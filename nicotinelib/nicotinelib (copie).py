from pynicotine import slskmessages
from pynicotine.pynicotine import NetworkEventProcessor
from pynicotine import utils
import time
import threading
from threading import Event
import urllib


def OnSoulSeek(self, url):
    try:
        user, file = urllib.url2pathname(url[7:]).split("/", 1)
        if file[-1] == "/":
            self.np.ProcessRequestToPeer(user, slskmessages.FolderContentsRequest(None, file[:-1].replace("/", "\\")))
        else:
            self.np.transfers.getFile(user, file.replace("/", "\\"), "")
    except:
        self.logMessage(("Invalid SoulSeek meta-url: %s") % url)


class MethodsEvent(_Event):
    """
    This class is used to pass information from Client Thread and Network Thread
    """
    def __init__(self, msg=None):
        super(_Event, self).__init__()
        self.msg = msg

    def getMsg(self):
        return self.msg

    def setMsg(self, msg):
        self.msg= msg


class NicotineConnection:
    """
    NicotineConnection is the actual core class of the project, that may be used by non gui applacations
    """
    def __init__(self, config, bindip=None):
        self.loginMethodEvent = MethodsEvent()
        self.joinRoomMethodEvent = MethodsEvent()
        self.serverConnectionEvent= MethodsEvent()
        self.bindip= bindip
        self.isinit=True
        self.np = NetworkEventProcessor(self, self.bindip, config)

        config = self.np.config.sections
        temp_modes_order = config["ui"]["modes_order"]
        utils.DECIMALSEP = config["ui"]["decimalsep"]
        utils.CATCH_URLS = config["urls"]["urlcatching"]
        utils.HUMANIZE_URLS = config["urls"]["humanizeurls"]
        utils.PROTOCOL_HANDLERS = config["urls"]["protocols"].copy()
        utils.PROTOCOL_HANDLERS["slsk"] = OnSoulSeek
        utils.USERNAMEHOTSPOTS = config["ui"]["usernamehotspots"]
        self.isinit=False
        # utils.NICOTINE = self
        # pynicotine.utils.log = self.logMessage

    def callback(self, msgs):
        if len(msgs) > 0 and  not self.isinit:
            for i in msgs:
                if i.__class__ in self.np.events:
                    if i.__class__ is slskmessages.ServerConn:
                        self.serverConnectionEvent.setMsg(i)
                        self.serverConnectionEvent.set()
                    self.np.events[i.__class__](i)
                else:
                    self.logMessage("No handler for class %s %s" % (i.__class__, vars(i)))

    def login(self, login, password, timeout):
        """
        This is the implementation of the SLSKProtocol login message https://nicotine-plus.org/wiki/SoulseekProtocol#ServerCode1
        :param login: the user name
        :param password: the user password in plaintext
        :param timeout:
        :return: see https://nicotine-plus.org/wiki/SoulseekProtocol#ServerCode1
        """
        # np.queue.put(slskmessages.Login(self.config.sections["server"]["login"], self.config.sections["server"]["passw"], 157))  # 155,
        self.np.queue.put(slskmessages.Login(login, password, 157))  # Puts the message into the network thread queue

        if not self.loginMethodEvent.wait(timeout):
            raise Exception("Login error")
        return self.loginMethodEvent.getMsg()


    def joinRoom(self, room, timeout=None):
        """
        Implementation of the SLSKprotocol JoinRoom message.
        :param room: the room to join, it migth be an existing room or a new room
        :param timeout: The
        :return:
        """
        self.np.queue.put(slskmessages.JoinRoom(room))  # Puts the message into the network thread queue
        return self.joinRoomMethodEvent.getMsg() if self.joinRoomMethodEvent.wait(timeout) else None


    def connectToServer(self, servername, serverport, timeout):

        self.np.queue.put(slskmessages.ServerConn(None, (servername, serverport)))  # Puts the connection message into the network thread queue
        if not self.serverConnectionEvent.wait(timeout):
            raise Exception("Couldnot connect to the server")

        return self.serverConnectionEvent.getMsg()

    def getPort(self):
        return self.port

    def setPort(self, port):
        self.port=port




def postTransferMsgs(self, msgs, curtime):
    trmsgs = []
    for (key, value) in self.transfermsgs.iteritems():
        trmsgs.append(value)
    msgs = trmsgs + msgs
    self.transfermsgs = {}
    self.transfermsgspostedtime = curtime
    return msgs



