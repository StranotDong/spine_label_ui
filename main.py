#get_ipython().run_line_magic('matplotlib', 'qt')
from argparse import ArgumentParser
from myApp import SpineLabellingApp
import matplotlib.pyplot as plt
#plt.switch_backend('qt5Agg')
import os
import sys
from os.path import join
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication
"""
Construct the ImgIDList
"""
def get_ImgIDList(root_dir):
    rst = []
    for root, dirs, files in os.walk(root_dir):     
        for file in files:
            if file.endswith(".dcm"):
                ##############################################################
#                 rst.append(file)
                ##############################################################
                rst.append(join(root,file))
    return rst
 
plt.close('all')
#img_root_dir = 'Spine_Example_Radiographs'
#ImageIDList = get_ImgIDList(img_root_dir)

parser = ArgumentParser()
parser.add_argument("-r", "--img-root-dir", type=str,
					help="the image root directory", default= 'Spine_Example_Radiographs')
parser.add_argument("-z", "--zoom", type=float,
					help="zoom basic scale, should > 1, default is 1.2", default=1.2)
parser.add_argument("-b", "--begin-image", default=None,
					help="begin at which image, default is the first untouched image")
parser.add_argument("-w", "--window-level", default=0.1, type=float,
					help="window level changing scale, the smaller, the slower, default is 0.3")
parser.add_argument("-d", "--debug-mode", action="store_true",
					help="whether turn on debug model",)
parser.add_argument("-f", "--csv-filename", type=str, default='SpineLabels.csv',
					help="the csv file and read in and save on, default name is SpineLabels.csv. If there is no such file, the program will create the file after you press the save button in UI",)
args = parser.parse_args()
# print(ImageIDList)
ImageIDList = get_ImgIDList(args.img_root_dir)

if __name__ == '__main__':

    app = QApplication(sys.argv)
#    QApplication.setStyle('Fusion')
#    app = QCoreApplication(sys.argv)
    main = SpineLabellingApp(args.img_root_dir, 
                             ImageIDList, 
                             args.csv_filename, 
                             zoom_base_scale=args.zoom,
                             begin=args.begin_image,
                             wl_scale=args.window_level,
                             debug_mode=args.debug_mode)
    main.show()

    sys.exit(app.exec_())
