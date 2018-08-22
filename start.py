import argparse
import os
import align.detect_face as detect_face
import cv2
import numpy as np
import tensorflow as tf
from lib.face_utils import judge_side_face
from lib.utils import Logger, mkdir
from src.sort import Sort
logger = Logger(__name__)


def main():
    global colours, img_size
    args = parse_args()
    #一个或多个视频存放路径
    root_dir = args.root_dir
    #采集并裁剪人脸保存路径
    output_path = args.output_path
    display = args.display
    mkdir(output_path)

    if display:
        colours = np.random.rand(32, 3)

    #初始化tracker
    tracker = Sort() 

    logger.info('start track and extract......')
    with tf.Graph().as_default():
        with tf.Session(
                config=tf.ConfigProto(gpu_options=tf.GPUOptions(allow_growth=True),
                                      log_device_placement=False)) as sess:
            pnet, rnet, onet = detect_face.create_mtcnn(sess, "align")

            margin = 50
            minsize = 60  
            threshold = [0.6, 0.7, 0.7]  
            factor = 0.709  
            frame_interval = 1# 每多少帧检测一次，默认3
            scale_rate = 1 #对输入frame进行resize
            show_rate = 1 #对输出frame进行resize

            for filename in os.listdir(root_dir):
                logger.info('all files:{}'.format(filename))

            #遍历所有mp4格式的视频文件
            for filename in os.listdir(root_dir):
                if filename.split('.')[1] != 'mp4':
                    continue
                video_name = os.path.join(root_dir, filename)
                directoryname = os.path.join(output_path, filename.split('.')[0])
                logger.info('video_name:{}'.format(video_name))

                cam = cv2.VideoCapture(video_name)
                c = 0
                while True:
                    final_faces = []
                    addtional_attribute_list = []
                    ret, frame = cam.read()
                    if not ret:
                        logger.warning("ret false")
                        break
                    if frame is None:
                        logger.warning("frame drop")
                        break

                    frame = cv2.resize(frame, (0, 0), fx=scale_rate, fy=scale_rate)
                    r_g_b_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    if c % frame_interval == 0:
                        img_size = np.asarray(frame.shape)[0:2]
                        faces, points = detect_face.detect_face(r_g_b_frame, minsize, pnet, rnet, onet, threshold,factor)
                        face_sums = faces.shape[0]

                        if face_sums > 0:
                            face_list = []
                            for i, item in enumerate(faces):
                                #检测人脸的置信度
                                f = round(faces[i, 4], 6)
                                if f > 0.95:
                                    det = np.squeeze(faces[i, 0:4])

                                    # face rectangle
                                    det[0] = np.maximum(det[0] - margin, 0)
                                    det[1] = np.maximum(det[1] - margin, 0)
                                    det[2] = np.minimum(det[2] + margin, img_size[1])
                                    det[3] = np.minimum(det[3] + margin, img_size[0])
                                    face_list.append(item)

                                    # face cropped
                                    bb = np.array(det, dtype=np.int32)
                                    frame_copy = frame.copy()
                                    cropped = frame_copy[bb[1]:bb[3], bb[0]:bb[2], :]

                                    # use 5 face landmarks  to judge the face is front or side
                                    squeeze_points = np.squeeze(points[:, i])
                                    tolist = squeeze_points.tolist()
                                    facial_landmarks = []
                                    for j in range(5):
                                        item = [tolist[j], tolist[(j + 5)]]
                                        facial_landmarks.append(item)

                                    #可视化关键点
                                    if args.face_landmarks:
                                        for (x, y) in facial_landmarks:
                                            cv2.circle(frame_copy, (int(x), int(y)), 3, (0, 0, 255), 2)
                                    #计算三个重要值用于判断正脸
                                    dist_rate, high_ratio_variance, width_rate = judge_side_face(np.array(facial_landmarks))

                                    # face addtional attribute(index 0:face score; index 1:0 represents front face and 1 for side face )
                                    item_list = [cropped, faces[i, 4], dist_rate, high_ratio_variance, width_rate]
                                    addtional_attribute_list.append(item_list)

                            final_faces = np.array(face_list)

                    trackers = tracker.update(final_faces, img_size, directoryname, addtional_attribute_list,r_g_b_frame)

                    c += 1
                    for d in trackers:
                        if display:
                            d = d.astype(np.int32)
                            cv2.rectangle(frame, (d[0], d[1]), (d[2], d[3]), colours[d[4] % 32, :] * 255, 5)
                            cv2.putText(frame, 'ID : %d' % (d[4]), (d[0] - 10, d[1] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.75,colours[d[4] % 32, :] * 255, 2)
                            
                    if display:
                        frame = cv2.resize(frame, (0, 0), fx=show_rate, fy=show_rate)
                        cv2.imshow("Frame", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break


def parse_args():
    """Parse input arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root_dir", type=str,default='./videos',
                        help='Path to the data directory containing aligned your face patches.')
    parser.add_argument('--output_path', type=str,
                        help='Path to save face',
                        default='facepics')
    parser.add_argument('--display', type=bool,
                        help='Display or not', default=True)
    parser.add_argument('--face_landmarks', type=bool,
                        help='draw 5 face landmarks on extracted face or not ', default=True)
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    main()
