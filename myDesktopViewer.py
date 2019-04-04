import qt5reactor
import sys
import os
import threading
import codecs
import signal
from twisted.internet.protocol import Protocol, Factory, ClientFactory
from twisted.python import log
from PyQt5.QtGui import QPainter, QIcon, QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QAction, QStyleFactory, QMainWindow, QWidget, QLabel, QLineEdit, QSizePolicy
import myDesktopClientProtocol as clientProtocol

log.startLogging(sys.stdout)

app = QApplication(sys.argv)

__applib__ = os.path.dirname(os.path.realpath(__file__))
__appicon__ = os.path.dirname(os.path.realpath(__file__))

qt5reactor.install()


class RDCToGUI(clientProtocol.rdc):
    def __init__(self):
        super().__init__()
        self.num = 0
        self.count = 0
        self.framerate_before = 0

    def connectionMade(self):
        self.factory.readyConnection(self)

    def vncRequestPassword(self):
        password = self.factory.password
        self.sendPassword(password)

    def commitFramebufferUpdate(self, framebuffer):
        self.factory.display.updateFramebuffer(framebuffer)
        self.framebufferUpdateRequest(
            width=self.factory.display.width, height=self.factory.display.height)

    def updateRates(self, framerate_label, datarate_label):
        divisor = 1
        datarate_text = "b/s"

        self.rates(self)
        framerate = self.framerate
        datarate = self.datarate

        if self.logged_in == 1 and self.framerate_before == 0 == framerate:
            self.framebufferUpdateRequest(
                width=800, height=800)
        if datarate > 1000000:
            divisor = 1000000
            rateText = "Mb/s"
        elif datarate > 1000:
            divisor = 1000
            rateText = "Kb/s"

        self.framerate_before = framerate

        framerate_label.setText(f"Framerate: {framerate}")
        datarate_label.setText(
            f"Datarate: {round(datarate / divisor, 2)} {datarate_text}")

        threading.Timer(1, self.updateRates, args=(self,
                                                   framerate_label, datarate_label)).start()


class RDCFactory(clientProtocol.RDCFactory):
    def __init__(self, display=None, password=None, shared=0):
        clientProtocol.RDCFactory.__init__(self, password, shared)
        self.display = display
        self.protocol = RDCToGUI

    def buildProtocol(self, addr):
        return clientProtocol.RDCFactory.buildProtocol(self, addr)

    def readyConnection(self, client):
        self.display.readyDisplay(client)

    def clientConnectionFailed(self, connector, reason):
        log.msg("Client connection failed!. (%s)" % reason.getErrorMessage())
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        log.msg("Client connection lost!. (%s)" % reason.getErrorMessage())
        reactor.stop()


class Display(QWidget):
    """
    this class for display remoteframebuffer and get the client events
    and then send the events to server, the include keyEvent, pointerEvent,
    mouseMoveEvent, clipboardEvent.
    """

    def __init__(self, parent=None):
        super(Display, self).__init__(parent)
        self.resize(1390, 780)
        self._pixelmap = QPixmap()
        self._remoteframebuffer = ""
        self._clipboard = app.clipboard()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.clientProtocol = None
        self.parent = parent

        #-------------------------------------#
        ## Use QLabel or QPainter to display ##
        #-------------------------------------#
        # self.viewPort = QLabel(self)
        # self.viewPort.setMaximumSize(self.size())
        # self.viewPort.setMinimumSize(self.size())
        # painter = QPainter(self)

    def readyDisplay(self, protocol):
        self.clientProtocol = protocol

    def paintEvent(self, event):
        """
        paint frame buffer in widget
        """
        painter = QPainter(self)
        if self._remoteframebuffer:
            framebuffer = codecs.decode(
                self._remoteframebuffer, 'unicode_escape').encode('ISO-8859-1')

            self._pixelmap.loadFromData(framebuffer)
            # painter.drawPixmap(0, 0, self._pixelmap)
            painter.drawPixmap(0, 0, self._pixelmap.scaled(
                self.size(), Qt.IgnoreAspectRatio))
        self.update()
        painter.end()

    def updateFramebuffer(self, pixelmap):
        self._remoteframebuffer = pixelmap[2:-1]
        # self._pixelmap.loadFromData(pixelmap.encode())
        # self.viewPort.setPixmap(self._pixelmap)
        # self.update()

    def keyPressEvent(self, event):
        key = event.key()
        print(key)
        flag = event.type()
        if self.clientProtocol is None:
            return
        self.clientProtocol.keyEvent(key, flag)
        self.update()

    def mousePressEvent(self, event):
        x, y = (event.pos().x(), event.pos().y())
        button = event.button()
        print(button)
        flag = event.type()
        if self.clientProtocol is None:
            return  # self.clientProtocol = self.parent.client.clientProto
        self.clientProtocol.pointerEvent(x, y, button, flag)
        print(self.clientProtocol.pointerEvent)

    def mouseReleaseEvent(self, event):
        x, y = (event.pos().x(), event.pos().y())
        button = event.button()
        flag = event.type()
        if self.clientProtocol is None:
            return  # self.clientProtocol = self.parent.client.clientProto
        self.clientProtocol.pointerEvent(x, y, button, flag)

    def mouseMoveEvent(self,  event):
        x, y = (event.pos().x(), event.pos().y())
        button = event.button()
        flag = event.type()
        if self.clientProtocol is None:
            return  # self.clientProtocol = self.parent.client.clientProto
        self.clientProtocol.pointerEvent(x, y, button, flag)

    def resizeEvent(self, event):
        """
        the remote framebuffer's size is according the client viewer size
        this may reduce the size of the images can be
        """
        size = event.size()
        self.width, self.height = (size.width(), size.height())


class myDesktopViewer(QMainWindow):
    def __init__(self,  parent=None):
        super(myDesktopViewer, self).__init__(parent)
        self.display = Display(self)
        self.setupUI()
        self.client = None

    def setupUI(self):
        self.setWindowTitle('myDesktop (viewer)')
        self.resize(1920, 1080)
        app.setStyle(QStyleFactory.create('fusion'))
        app.setPalette(app.style().standardPalette())

        self.datarateLabel = QLabel()
        self.framerateLabel = QLabel()
        self.datarateLabel.setText("Datarate: ")
        self.framerateLabel.setText("Framerate: ")

        qualitiyLabel = QLabel()
        qualitiyLabel.setText("Quality: ")
        qualityInput = QLineEdit()
        qualityInput.setText("20")
        qualityInput.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        qualityInput.setMinimumWidth(30)

        # add action on application
        self.startAction = QAction(
            QIcon(os.path.join(__appicon__, 'icons', 'Start.png')), 'Start', self)
        self.stopAction = QAction(
            QIcon(os.path.join(__appicon__, 'icons', 'Stop.png')),  'Stop',  self)
        self.startAction.setToolTip('Start connection')
        self.stopAction.setToolTip('Stop connection')
        self.startAction.triggered.connect(self.connectionStart)
        self.stopAction.triggered.connect(self.connectionStop)

        # add a toolbar
        self.toolbar = self.addToolBar('')
        self.toolbar.addAction(self.stopAction)
        self.toolbar.addAction(self.startAction)
        self.toolbar.addWidget(self.datarateLabel)
        self.toolbar.addWidget(self.framerateLabel)
        self.toolbar.addWidget(qualitiyLabel)
        self.toolbar.addWidget(qualityInput)

        displayWidget = QWidget()
        vbox = QVBoxLayout(displayWidget)
        vbox.addWidget(self.display)
        # vbox.setMargin(0)
        self.setCentralWidget(displayWidget)

    def connectionStart(self):
        self.client = RDCFactory(display=self.display, password='1234')
        reactor.connectTCP('127.0.0.1', 5000, self.client)
        threading.Timer(1, self.client.protocol.updateRates, args=(self.client.protocol,
                                                                   self.framerateLabel, self.datarateLabel)).start()

    def connectionStop(self):
        clientProtocol.logged_in = 0
        reactor.stop()

    def closeEvent(self, event):
        self.connectionStop()
        self.close()
        os._exit(0)


if __name__ == '__main__':
    from twisted.internet import reactor
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    mydesktop = myDesktopViewer()
    mydesktop.show()
    reactor.run()  # enter mainloop
