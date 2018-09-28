
import tensorflow as tf
from network.config import cfg
from tensorflow.python.client import timeline
from tools.timer import Timer
from tools.data_visualize import pcd_vispy,vispy_init,test_show_rpn_tf,BoxAry_Theta,pcd_vispy_standard
import numpy
import numpy as np
VISION_DEBUG = True
USE_ROS = True

class CubicNet_Test(object):
    def __init__(self, network, data_set, args):
        self.saver = tf.train.Saver(max_to_keep=100)
        self.net = network
        self.dataset = data_set
        self.args = args
        self.epoch = self.dataset.input_num

    def format_convertor(self,type,inputs):
        if type=='output':
            net_outs=inputs

            cube_score_det = net_outs[:,0:2]
            cube_cls_det=(cube_score_det[:,0]<cube_score_det[:,1]).astype(np.float32).reshape(-1,1)

            cube_size_det = net_outs[:,2:5]+ np.array([3.88311640418,1.62856739989,1.52563191462])

            cube_ctr_det = net_outs[:,5:8]

            cube_yaw_component_det= net_outs[:,8:10]

            yaw = np.arctan2(cube_yaw_component_det[:,1], cube_yaw_component_det[:,0])

            cube_yaw_det = yaw.reshape(-1,1)

            return np.hstack((cube_cls_det,cube_ctr_det,cube_size_det,cube_yaw_det))

    def testing(self, sess, test_writer):
        # =======================================
        if USE_ROS:
            import rospy
            from sensor_msgs.msg import PointCloud,Image
            from visualization_msgs.msg import MarkerArray, Marker
            from tools.data_visualize import Boxes_labels_Gen, Image_Gen,PointCloud_Gen

            rospy.init_node('rostensorflow')
            pub = rospy.Publisher('prediction', PointCloud, queue_size=1000)
            img_pub = rospy.Publisher('images_rgb', Image, queue_size=1000)
            box_pub = rospy.Publisher('label_boxes', MarkerArray, queue_size=1000)
            rospy.loginfo("ROS begins ...")
        # =======================================
        with tf.name_scope("Inference"):
            # RNet_rpn_yaw_pred = self.net.get_output('RNet_theta')[1]
            # RNet_rpn_yaw_gt_delta = self.net.get_output('cubic_grid')[1]
            # RNet_rpn_yaw_pred_toshow = RNet_rpn_yaw_pred+RNet_rpn_yaw_gt_delta
            rpn_rois_3d = self.net.get_output('rpn_rois')[1]

        with tf.name_scope('view_rpn_bv_tb'):
            # roi_bv = self.net.get_output('rpn_rois')[0]
            # data_bv = self.net.lidar_bv_data
            # image_rpn = tf.reshape(test_show_rpn_tf(data_bv,roi_bv), (1, 601, 601, -1))
            # tf.summary.image('lidar_bv_test', image_rpn)
            feature = tf.reshape(tf.transpose(tf.reduce_sum(self.net.watcher[0],axis=-2),[2,0,1]),[-1,30,30,1])
            tf.summary.image('shape_extractor_P1', feature,max_outputs=50)
            # feature = tf.reshape(tf.transpose(tf.reduce_sum(self.net.watcher[1],axis=-1),[2,0,1]),[-1,30,30,1])
            # tf.summary.image('shape_extractor_P2', feature,max_outputs=10)
            # feature = tf.reshape(tf.transpose(tf.reduce_sum(self.net.watcher[-1],axis=-1),[2,0,1]),[-1,30,30,1])
            # tf.summary.image('shape_extractor_N1', feature,max_outputs=3)
            # feature = tf.reshape(tf.transpose(tf.reduce_sum(self.net.watcher[-2],axis=-1),[2,0,1]),[-1,30,30,1])
            # tf.summary.image('shape_extractor_N2', feature,max_outputs=3)
            merged = tf.summary.merge_all()
            glb_var = tf.global_variables()
            a=0
        with tf.name_scope('load_weights'):
            print 'Loading pre-trained model weights from {:s}'.format(self.args.weights)
            self.net.load_weigths(self.args.weights, sess, self.saver)
            self.net.load_weigths(self.args.weights_cube, sess, self.saver,specical_flag=True)

        vispy_init()  # TODO: Essential step(before sess.run) for using vispy beacuse of the bug of opengl or tensorflow
        timer = Timer()

        cubic_cls_score = self.net.get_output('cubic_cnn')[:,0:2]
        net_outs = self.net.get_output('cubic_cnn')
        # cube_size_scale_det=self.net.get_output('cubic_cnn')[:,2:5]
        # cube_ctr_det = self.net.get_output('cubic_cnn')[:,5:8]
        # cube_yaw_component_det= self.net.get_output('cubic_cnn')[:,8:10]

        for idx in range(0,self.epoch,1):
            # index_ = input('Type a new index: ')
            blobs = self.dataset.get_minibatch(idx)
            feed_dict = {
                self.net.lidar3d_data: blobs['lidar3d_data'],
                self.net.lidar_bv_data: blobs['lidar_bv_data'],
                self.net.im_info: blobs['im_info'],
                # self.net.calib: blobs['calib']
            }
            run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
            run_metadata = tf.RunMetadata()
            timer.tic()
            net_outs_,cubic_cls_score_,rpn_rois_3d_,summary = sess.run([net_outs,cubic_cls_score, rpn_rois_3d, merged], feed_dict=feed_dict, options=run_options, run_metadata=run_metadata)
            timer.toc()
            net_outs_box=self.format_convertor(type="output",inputs=net_outs_)

            if idx % 3 ==0 and cfg.TEST.DEBUG_TIMELINE:
                # chrome://tracing
                trace = timeline.Timeline(step_stats=run_metadata.step_stats)
                trace_file = open(cfg.LOG_DIR + '/' +'testing-step-'+ str(idx).zfill(7) + '.ctf.json', 'w')
                trace_file.write(trace.generate_chrome_trace_format(show_memory=False))
                trace_file.close()
            if idx % cfg.TEST.ITER_DISPLAY == 0:
                pass
                print 'Test: %06d/%06d  speed: %.4f s / iter' % (idx+1, self.epoch, timer.average_time)
            if VISION_DEBUG:
                scan = blobs['lidar3d_data']
                img = blobs['image_data']
                cubic_cls_value = cubic_cls_score_.argmax(axis=1)

                if USE_ROS:
                    import numpy as np
                    from tools.data_visualize import PointCloud_Gen,Boxes_labels_Gen,Image_Gen
                    pointcloud = PointCloud_Gen(scan)

                    label_boxes = Boxes_labels_Gen(rpn_rois_3d_, ns='Predict')
                    img_ros = Image_Gen(img)
                    pub.publish(pointcloud)
                    img_pub.publish(img_ros)
                    box_pub.publish(label_boxes)
                else:
                    boxes = BoxAry_Theta(pre_box3d=rpn_rois_3d_,pre_cube_cls=cubic_cls_value)  # RNet_rpn_yaw_pred_toshow_  rpn_rois_3d_[:,-1]
                    # pcd_vispy(scan, img, boxes,index=idx,
                    #           save_img=True,#cfg.TEST.SAVE_IMAGE,
                    #           visible=False,
                    #           name='CubicNet testing')
                    a=cubic_cls_value.reshape(-1,1)
                    b=rpn_rois_3d_[:,0:6]
                    c=numpy.zeros(shape=(cubic_cls_value.shape[0],1))
                    boxes=numpy.hstack((a,b,c))
                    settings={'fov': 0.0, 'elevation': 57.0, 'center': (6.5, -0.5, 9.0), 'azimuth': -126.0, 'scale_factor': 63.0, 'roll': 0.0}
                    pcd_vispy_standard(scan,img,index=idx,
                                                save_img=True,#cfg.TEST.SAVE_IMAGE,
                                                visible=False,
                                                boxes=boxes,
                                                lidar_view_set=settings)
            if idx % 1 == 0 and cfg.TEST.TENSORBOARD:
                test_writer.add_summary(summary, idx)
                pass
        print 'Testing process has done, happy every day !'


def network_testing(network, data_set, args):
    net = CubicNet_Test(network, data_set, args)
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True

    with tf.Session(config=config) as sess:
        test_writer = tf.summary.FileWriter(cfg.LOG_DIR, sess.graph, max_queue=300)
        net.testing(sess, test_writer)

