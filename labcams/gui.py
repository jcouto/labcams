# Qt imports
import sys
import os
from .utils import display
from .cams import *

try:
    from PyQt5.QtWidgets import (QWidget,
                                 QApplication,
                                 QGridLayout,
                                 QFormLayout,
                                 QVBoxLayout,
                                 QTabWidget,
                                 QCheckBox,
                                 QTextEdit,
                                 QSlider,
                                 QLabel,
                                 QAction,
                                 QMenuBar,
                                 QGraphicsView,
                                 QGraphicsScene,
                                 QGraphicsItem,
                                 QGraphicsLineItem,
                                 QGroupBox,
                                 QTableWidget,
                                 QMainWindow,
                                 QDockWidget,
                                 QFileDialog)
    from PyQt5.QtGui import QImage, QPixmap,QBrush,QPen,QColor
    from PyQt5.QtCore import Qt,QSize,QRectF,QLineF,QPointF
    print("Using Qt5 framework.")
except:
    from PyQt4.QtGui import (QWidget,
                             QApplication,
                             QAction,
                             QMenuBar,
                             QGridLayout,
                             QFormLayout,
                             QVBoxLayout,
                             QCheckBox,
                             QTextEdit,
                             QSlider,
                             QLabel,
                             QGraphicsView,
                             QGraphicsScene,
                             QGraphicsItem,
                             QGraphicsLineItem,
                             QGroupBox,
                             QTableWidget,
                             QFileDialog,
                             QImage,
                             QPixmap)
    from PyQt4.QtCore import Qt,QSize,QRectF,QLineF,QPointF


class LabCamsGUI(QMainWindow):
    app = None
    cams = []
    def __init__(self,app = None, camDescriptions = []):
        super(LabCamsGUI,self).__init__()
        print('Starting labcams interface.')
        self.app = app
        self.cam_descriptions = camDescriptions
        # Init cameras
        self.cam_descriptions = range(3)
        for c,cam in enumerate(self.cam_descriptions):
            display("Connecting to " + str(c) + ' camera')
            self.cams.append(DummyCam())

        self.initUI()

    def experimentMenuTrigger(self,q):
        print(q.text()+ "clicked. ")
        
    def initUI(self):
        # Menu
        bar = self.menuBar()
        editmenu = bar.addMenu("Experiment")
        editmenu.addAction("New")
        editmenu.triggered[QAction].connect(self.experimentMenuTrigger)
        self.setWindowTitle("LabCams")
        self.tabs = []
        self.camwidgets = []
        for c,cam in enumerate(self.cams):
            self.tabs.append(QDockWidget("Camera: "+str(c),self))
            self.tabs[-1].setWidget(QWidget())
            self.tabs[-1].setFloating(False)
            self.camwidgets.append({})
#            self.camwidgets[-1]['scene'] = QGraphicsScene()
#            self.camwidgets[-1]['view'] = QGraphicsView(
#                self.camwidgets[-1]['scene'])
#            img = np.ones([cam.h,cam.w])
#            self.camwidgets[-1]['view'].setImage(img)
            self.addDockWidget(Qt.RightDockWidgetArea,self.tabs[-1])
            display('Init view: ' + str(c))          
        self.show()

def main():
    app = QApplication(sys.argv)
    w = LabCamsGUI(app = app)
    sys.exit(app.exec_())

if __name__ == '__main__':
    print('GUI test.')
    main()
