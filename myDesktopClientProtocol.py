#!/usr/bin/python
"""
This is RDC(Remote Desktop Control) protocol
"""
import lzma
from twisted.internet.protocol import Protocol, ClientFactory
from twisted.python import log
from message_defines import messageTypes as msgTypes


class rdc(Protocol):

    def __init__(self):
        self._packet = ""
        self._expected_len = 0
        self._cnt_framerate = 0
        self._cnt_datarate = 0
        self.framerate = 0
        self.datarate = 0
        self.logged_in = 0

    def _doClientInitialization(self):
        self.logged_in = 1
        self.framebufferUpdateRequest(width=800, height=600)

    def dataReceived(self, data):
        self.addDataSize(len(data))
        self._packet += data.decode('latin1')
        if self._expected_len == 0:
            buffer = self._packet.split('@')
            self._expected_len, self._packet = int(
                buffer[0]), "@".join(buffer[1:])

        packet_len = len(self._packet)
        packet = self._packet
        packet_expected = self._expected_len

        if packet_expected < packet_len or packet_expected == packet_len:
            # If two Messages are in one Packet --> split them up
            self._packet = packet[packet_expected:]
            packet = packet[:packet_expected]

            self._expected_len = 0

            cmd = eval(packet)
            for key in cmd.keys():
                args = cmd[key]
                self.handler(key, args)

        if packet_len == packet_expected:
            self._packet = ""

    def _pack(self, message, **kw):
        message = f"{{{message}: {kw}}}"
        message_len = len(message)
        message = f"{message_len}@{message}"
        return message.encode('latin1')

    def handler(self, option, args):
        log.msg(f'MessageType: {option}')
        if option == msgTypes.AUTHENTICATION:
            print('Auth   ', args)
            self._handleAuth(**args)

        elif option == msgTypes.FRAME_UPDATE:
            self._handleFramebufferUpdate(**args)

        elif option == msgTypes.COPY_TEXT:
            self.handleCopyText(**args)

        elif option == msgTypes.CUT_TEXT:
            self._handleServerCutText(**args)

        elif option == msgTypes.TEXT_MESSAGE:
            self.handleServerTextMessage(**args)

        elif option == msgTypes.AUTH_RESULT:
            self._handleVNCAuthResult(**args)

    #--------------------------#
    ## Handle server messages ##
    #--------------------------#
    def _handleAuth(self, block):
        if block == 0:  # fail
            pass

        elif block == 1:
            self._doClientInitialization()

        elif block == 2:
            self._handleVNCAuth()

    def _handleVNCAuth(self):
        self.vncRequestPassword()

    def _handleVNCAuthResult(self, block):
        if block == 0:   # OK
            self._doClientInitialization()

        elif block == 1:  # Failed
            self.vncAuthFailed("autenthication failed")
            # self.transport.loseConnection( )

        elif block == 2:  # Too many
            self.vncAuthFailed("too many tries to log in")
            self.transport.loseConnection()

        else:
            # log.msg(f"unknown auth response {auth}\n")
            pass

    def _handleFramebufferUpdate(self, framebuffer):
        self.incFramerate()
        framebuffer = self.decompressFramebuffer(framebuffer)
        self.commitFramebufferUpdate(framebuffer)

    def decompressFramebuffer(self, framebuffer):
        return lzma.decompress(framebuffer.encode('latin1'), lzma.FORMAT_XZ).decode('latin1')

    def vncAuthFailed(self, reason):
        log.msg(f'Cannot connect: {reason}')

    #-----------------------------#
    ## Client >> Server messages ##
    #-----------------------------#
    def framebufferUpdateRequest(self, width, height):
        self.transport.write(self._pack(
            msgTypes.FRAME_UPDATE, width=width, height=height))

    def keyEvent(self, key, flag):
        self.transport.write(self._pack(
            msgTypes.KEY_EVENT, key=key, flag=flag))

    def pointerEvent(self, x, y, buttonmask, flag=None):
        self.transport.write(self._pack(
            msgTypes.POINTER_EVENT, x=x, y=y, buttonmask=buttonmask, flag=flag))

    def clientCutText(self, text):
        log.msg("clientCutText; text=%s" % (text))
        self.transport.write(self._pack(msgTypes.CUT_TEXT, text=text))

    def sendPassword(self, password):
        self.transport.write(self._pack(
            msgTypes.AUTHENTICATION, client_password=password))

    def rates(self):
        self.setRates(self)
        self.resetCounter(self)

    def setRates(self):
        self.framerate = self._cnt_framerate
        self.datarate = self._cnt_datarate

    def resetCounter(self):
        self._cnt_datarate = 0
        self._cnt_framerate = 0

    def incFramerate(self):
        self._cnt_framerate += 1

    def addDataSize(self, size):
        self._cnt_datarate += size
    #----------------------------#
    ## Overiding on application ##
    #----------------------------#

    def commitFramebufferUpdate(self, framebuffer):
        pass


class RDCFactory(ClientFactory):
    protocol = rdc

    def __init__(self, password=None, shared=0):
        self.password = password
        self.shared = shared
