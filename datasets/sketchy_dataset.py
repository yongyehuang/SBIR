from torch.utils import data
import numpy as np
from torchvision import transforms
from util.util import to_rgb
import os,re,json
import cv2
from PIL import Image
class SketchyDataset(data.Dataset):
    def name(self):
        return "sketchy"
    def __init__(self, opt):# root,photo_types,sketch_types,batch_size, mode="train", train_split=2000,  pair_inclass_num=2,pair_outclass_num=3):
        self.opt = opt
        root = opt.data_root
        photo_types = opt.sketchy_photo_types
        sketch_types = opt.sketchy_sketch_types
        mode = opt.phase
        self.mode = mode

        transforms_list = []
        if self.opt.random_crop:
            transforms_list.append(transforms.Resize((256,256)))
            transforms_list.append(transforms.RandomCrop((self.opt.scale_size, self.opt.scale_size)))
        if self.opt.flip:
            transforms_list.append(transforms.RandomHorizontalFlip())
        transforms_list.append(transforms.Resize((self.opt.scale_size, self.opt.scale_size)))    
        transforms_list.append(transforms.ToTensor())
        #transforms_list.append(transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)))
        self.transform_fun = transforms.Compose(transforms_list)
        self.test_transform_fun = transforms.Compose([transforms.Resize((self.opt.scale_size, self.opt.scale_size))])

        self.sketch_imgs = []
        self.photo_imgs = []
        self.photo_neg_imgs = []
        
        self.fg_labels = []
        self.labels = []

        if mode == "train":
            start, end = 0, 95
        elif mode == 'test':
            start, end = 95, 100
        photo_roots = [root+photo_type for photo_type in photo_types]
        print(photo_roots)
        for photo_root in photo_roots:
            print(photo_root)
            fg_label = 0
            label = 0
            for photo_root, subFolders, files in os.walk(photo_root):
                photo_pat = re.compile("n.+\.jpg")
                photo_imgs = list(filter(lambda fname:photo_pat.match(fname),files))
                if len(photo_imgs) == 0:
                    print(photo_root)
                    continue
                sketch_imgs = []
                for i, photo_img in enumerate(photo_imgs):
                    if i < start or i >= end:
                        continue
                    for sketch_type in sketch_types:
                        sketch_root = photo_root[:photo_root.find("photo")] + "sketch/"+sketch_type+"/"+photo_root[photo_root.rfind("/")+1:]
                        for i in range(1,20):
                            sketch_img = photo_img[:photo_img.find(".jpg")] + "-" + str(i) + ".png"
                            sketch_path = os.path.join(sketch_root, sketch_img)
                            if os.path.exists(sketch_path):
                                self.photo_imgs.append(os.path.join(photo_root,photo_img))
                                self.sketch_imgs.append(sketch_path)
                                self.photo_neg_imgs.append(os.path.join(photo_root,photo_img))
                                self.fg_labels.append(fg_label)
                                self.labels.append(label)
                            else:
                                break
                    fg_label += 1
                label += 1
        self.n_labels = label
        self.n_fg_labels = fg_label
        self.ori_photo_imgs  = self.photo_imgs.copy()
        self.ori_sketch_imgs = self.sketch_imgs.copy()
        self.ori_fg_labels = self.fg_labels.copy()
        self.ori_labels = self.labels.copy()
        self.query_what = self.opt.query_what
        # self.labels_dict = [{} for i in range(self.n_labels)]
        # for i, label in enumerate(self.labels):
        #    # print(label)
        #     self.labels_dict[label].append(i)
        # self.fg_labels_dict = [{} for i in range(self.n_fg_labels)]
        # for i, fg_label in enumerate(self.fg_labels):
        #    # print(fg_label)
        #     self.fg_labels_dict[fg_label].append(i)
        self.labels_dict = {i:[] for i in range(self.n_labels)}
        for i, label in enumerate(self.labels):
            self.labels_dict[label].append(i)
        self.fg_labels_dict = {i:[] for i in range(self.n_fg_labels)}
        for i, fg_label in enumerate(self.fg_labels):
            self.fg_labels_dict[fg_label].append(i)
        print("Total Sketchy Class:{}, fg class: {}".format(self.n_labels, self.n_fg_labels))
        if self.query_what == "image":
            self.query_image()
        elif self.query_what == "sketch":
            self.query_sketch()  

        print("{} pairs loaded.".format(len(self.photo_imgs)))
        self.generate_triplet_all()
        if mode == "test":
            self.fg_labels = []
            for i in range(len(self.photo_imgs)):
                self.fg_labels.append(i % self.opt.batch_size)


        print("{} pairs loaded. After generate triplet".format(len(self.photo_imgs)))
    def generate_triplet_all(self):
        pair_inclass_num, pair_outclass_num = self.opt.pair_num
        if self.opt.phase == "train" and not self.opt.model == 'cls_model' and not self.opt.neg_flag == "moderate" :
            if self.opt.task == 'fg_sbir':
                self.generate_triplet(pair_inclass_num,pair_outclass_num)
            elif self.opt.task == 'cate_sbir':
                self.generate_cate_triplet(pair_inclass_num,pair_inclass_num)        
    def query_image(self):
        self.query_imgs = self.ori_sketch_imgs
        self.search_imgs = self.ori_photo_imgs
        self.search_neg_imgs = self.ori_photo_imgs.copy()
        self.labels = self.ori_labels.copy()
        self.fg_labels = self.ori_fg_labels.copy()
        self.load_search = self.load_image
        self.load_query = self.load_sketch
        print("Query is Sketch Search image")
    def query_sketch(self):
        self.query_imgs = self.ori_photo_imgs
        self.search_imgs = self.ori_sketch_imgs
        self.search_neg_imgs = self.ori_sketch_imgs.copy()
        self.labels = self.ori_labels.copy()
        self.fg_labels = self.ori_fg_labels.copy()
        self.load_query = self.load_image
        self.load_search = self.load_sketch
        print("Query is Image Search Sketch")
    def load_image(self, pil):
        def show(mode, pil_numpy):
            print(mode, len(",".join([str(i) for i in pil_numpy.flatten() if i != 0])))

        if self.opt.image_type == 'RGB':
            pil = pil.convert('RGB')
            pil_numpy = np.array(pil)
        elif self.opt.image_type == 'GRAY':
            pil = pil.convert('L')
            pil_numpy = np.array(pil)
        elif self.opt.image_type == 'EDGE':
            pil = pil.convert('L')
            pil_numpy = np.array(pil)
            #show('edge', pil_numpy)
            pil_numpy = cv2.Canny(pil_numpy, 0, 200)

        #print('image{}'.format(pil_numpy.shape))
        #if self.opt.image_type == 'GRAY' or self.opt.image_type == 'EDGE':
        #    pil_numpy = pil_numpy.reshape(pil_numpy.shape + (1,))
        #pil_numpy = cv2.resize(pil_numpy, (self.opt.scale_size, self.opt.scale_size))
        #if self.opt.sketch_type == 'GRAY' or self.opt.image_type == 'EDGE':
        #    pil_numpy = pil_numpy.reshape(pil_numpy.shape[:2])
        transform_fun = self.transform_fun if self.mode == 'train' else self.test_transform_fun
        if transform_fun is not None :
            pil = Image.fromarray(pil_numpy)
            pil_numpy = transform_fun(pil)
        return pil_numpy

    def load_sketch(self, pil):
        def show(mode, pil_numpy):
            print(mode, len(",".join([str(i) for i in pil_numpy.flatten() if i != 0])))
        pil = pil.convert('L')
        pil_numpy = np.array(pil)



        if self.opt.sketch_type == 'RGB':
            pil_numpy = to_rgb(pil_numpy)   

        transform_fun = self.transform_fun if self.mode == 'train' else self.test_transform_fun
        if transform_fun is not None:
            pil = Image.fromarray(pil_numpy)
            pil_numpy = transform_fun(pil)
        
        return pil_numpy


    def transform(self, pil):
        pil_numpy = np.array(pil)
        if len(pil_numpy.shape) == 2:
            pil_numpy = to_rgb(pil_numpy)
            #pil_numpy = np.tile(pil_numpy,3).reshape(pil_numpy.shape+(-1,))
        elif pil_numpy.shape[2] == 4:
            pil_numpy = to_rgb(pil_numpy[:,:,3])
            #pil_numpy = np.tile(pil_numpy[:,:,3],3).reshape(pil_numpy.shape[0:2]+(-1,))
        if self.opt.image_type == 'GRAY':
            gray_pil = Image.fromarray(pil_numpy)
            pil_numpy = np.array(gray_pil.convert('L'))

        pil_numpy = cv2.resize(pil_numpy,(self.opt.scale_size,self.opt.scale_size))
        if self.opt.image_type == 'GRAY':
            pil_numpy = pil_numpy.reshape(pil_numpy.shape + (1,))
        if self.transform_fun is not None:
            pil_numpy = self.transform_fun(pil_numpy)
        return pil_numpy

    def __len__(self):
        return len(self.photo_imgs)

    def __getitem__(self,index):
        search_img,query_img,search_neg_img,fg_label,label = self.search_imgs[index], self.query_imgs[index], self.search_neg_imgs[index], self.fg_labels[index], self.labels[index]
        search_pil,query_pil,search_neg_pil = Image.open(search_img), Image.open(query_img), Image.open(search_neg_img)
        #if self.transform is not None:
        search_pil = self.load_search(search_pil)
        query_pil = self.load_query(query_pil)
        search_neg_pil = self.load_search(search_neg_pil)
        return query_pil,search_pil,search_neg_pil, label, fg_label,label

    def generate_cate_triplet(self, pair_inclass_num, pair_outclass_num):
        query_imgs, search_imgs, search_neg_imgs, fg_labels, labels = [],[],[],[],[]

        labels_dict = [[] for i in range(self.n_labels)]
        for i, label in enumerate(self.labels):
            labels_dict[label].append(i)

        for i, (query_img, search_img, fg_label, label) in enumerate(zip(self.query_imgs, self.search_imgs, self.fg_labels, self.labels)):

            
            for t, l in enumerate(labels_dict[label]):
                if l != i and t < pair_inclass_num:
                    for j in range(pair_outclass_num):
                        ind_label = np.random.randint(self.n_labels)
                        while ind_label == label:

                            ind_label = np.random.randint(self.n_labels)
                        #print(ind_label)
                        ind = np.random.randint(len(labels_dict[ind_label]))
                    
                        query_imgs.append(query_img)
                        search_imgs.append(self.search_imgs[l])
                        search_neg_imgs.append(self.search_imgs[labels_dict[ind_label][ind]])
                        fg_labels.append(fg_label)
                        labels.append(label)

        self.query_imgs, self.search_neg_imgs, self.search_imgs, self.fg_labels, self.labels = query_imgs, search_neg_imgs, search_imgs, fg_labels, labels

           

    def generate_triplet(self, pair_inclass_num,pair_outclass_num=0):
        query_imgs, search_neg_imgs, search_imgs, fg_labels, labels = [],[],[],[],[]

        for i, (query_img, search_img, fg_label, label) in enumerate(zip(self.query_imgs, self.search_imgs, self.fg_labels, self.labels)):
            num = len(self.labels_dict[label])
            inds = [self.labels_dict[label].index(i)]
            for j in range(pair_inclass_num):
                ind = np.random.randint(num)
                while ind in inds or ind in self.fg_labels_dict[fg_label]:
                    ind = np.random.randint(num)
                inds.append(ind)
                query_imgs.append(query_img)
                search_neg_imgs.append(self.search_imgs[self.labels_dict[label][ind]])
                search_imgs.append(search_img)
                fg_labels.append(fg_label)
                labels.append(label)

        num = len(self.search_imgs)
        for i, (query_img, search_img, fg_label, label) in enumerate(zip(self.query_imgs, self.search_imgs, self.fg_labels, self.labels)):
            inds = [i]
            for j in range(pair_outclass_num):
                ind = np.random.randint(num)
                while ind in inds or ind in self.fg_labels_dict[fg_label] or ind in self.labels_dict[label]:
                    ind = np.random.randint(num)
                inds.append(ind)
                query_imgs.append(query_img)
                search_neg_imgs.append(self.search_imgs[ind])
                search_imgs.append(search_img)
                fg_labels.append(fg_label)
                labels.append(label)

        self.query_imgs, self.search_neg_imgs, self.search_imgs, self.fg_labels, self.labels = query_imgs, search_neg_imgs, search_imgs, fg_labels, labels
