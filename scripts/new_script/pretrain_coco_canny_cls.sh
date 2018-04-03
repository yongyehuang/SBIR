python train.py --data_root /home/lhy/datasets/coco2017 --dataset_type coco --checkpoints_dir checkpoints/new_experiment --name attention_pretrain_coco_canny --model cls_model --feature_model attention --feat_size 512 --phase train --num_epoch 30 --n_labels 1000 --n_attrs 1000 --scale_size 225 --image_type EDGE --sketch_type GRAY --batch_size 100 --gpu_ids 2 --retrieval_now --flip \
2>&1 |tee -a log/new_log/pretrain_coco_canny_cls.log