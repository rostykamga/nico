# -*- coding: utf-8 -*-
#
# COPYRIGHT (c) 2016 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (c) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2009 Hedonist <ak@sensi.org>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import gettext


from pynicotine.pynicotine import NetworkEventProcessor
from pynicotine import slskmessages
from pynicotine import slskproto

import urllib
import signal
import re

from pynicotine.config import *
import utils
import pynicotine.utils
from utils import AppendLine,  PopupMenu, Humanize, HumanSpeed

from dirchooser import ChooseFile, SaveFile
from pynicotine.logfacility import log
from entrydialog import *
from pynicotine.upnp import UPnPPortMapping
from threading import Event
import time

#from pynicotine.api.chatrooms import RoomsControl


class roomlist:

    def __init__(self, frame):

        self.frame = frame
        self.wTree = gtk.glade.XML(os.path.join(os.path.dirname(os.path.realpath(__file__)), "roomlist.glade"), None)

        widgets = self.wTree.get_widget_prefix("")
        for i in widgets:
            name = gtk.glade.get_widget_name(i)
            self.__dict__[name] = i
        self.RoomList.destroy()
        # self.RoomsList is the TreeView
        self.wTree.signal_autoconnect(self)
        self.search_iter = None
        self.query = ""
        self.room_model = self.RoomsList.get_model()
        self.FindRoom.connect("clicked", self.OnSearchRoom)

    def OnCreateRoom(self, widget):
        room = widget.get_text()
        if not room:
            return
        self.frame.np.queue.put(slskmessages.JoinRoom(room))
        widget.set_text("")

    def OnSearchRoom(self, widget):

        if self.room_model is not self.RoomsList.get_model():
            self.room_model = self.RoomsList.get_model()
            self.search_iter = self.room_model.get_iter_root()

        room = self.SearchRooms.get_text().lower()

        if not room:
            return

        if self.query == room:
            if self.search_iter is None:
                self.search_iter = self.room_model.get_iter_root()
            else:
                self.search_iter = self.room_model.iter_next(self.search_iter)
        else:
            self.search_iter = self.room_model.get_iter_root()
            self.query = room

        while self.search_iter:
            room_match, size = self.room_model.get(self.search_iter, 0, 1)
            if self.query in room_match.lower():
                path = self.room_model.get_path(self.search_iter)
                self.RoomsList.set_cursor(path)
                break
            self.search_iter = self.room_model.iter_next(self.search_iter)



class nicotineapi(gobject.GObject):
    def __init__(self, config, bindip=None):

        gobject.GObject.__init__(self)

        self.clip_data = ""
        self.configfile = config
        self.transfermsgs = {}
        self.transfermsgspostedtime = 0
        self.manualdisconnect = 0
        self.away = 0
        self.exiting = 0
        self.startup = True
        self.current_tab = 0
        self.rescanning = 0
        self.brescanning = 0
        self.needrescan = 0
        self.autoaway = False
        self.awaytimer = None
        self.bindip = bindip
        self.got_focus = False
        self.isinit = True
        self.stats = {}
        self.serverConnectionEvent = Event()
        self.getUserAddressEvent = Event()
        self.getRoomlistEvent = Event()
        self.searchResultEvent = Event()
        self.sharedfilelistresultEvent = Event()
        self.recommendationusers={}
        self.listeners= {}
        self.nbsocket=0

        self.np = NetworkEventProcessor(self, self.callback, self.logMessage, self.SetStatusText, self.bindip, config)
        config = self.np.config.sections
        self.np.waitport= self.waitport
        #self.np.IncPort(slskmessages.IncPort(self.waitport))

        self.temp_modes_order = config["ui"]["modes_order"]
        utils.DECIMALSEP = config["ui"]["decimalsep"]
        utils.CATCH_URLS = config["urls"]["urlcatching"]
        utils.HUMANIZE_URLS = config["urls"]["humanizeurls"]
        utils.PROTOCOL_HANDLERS = config["urls"]["protocols"].copy()
        utils.PROTOCOL_HANDLERS["slsk"] = self.OnSoulSeek
        utils.USERNAMEHOTSPOTS = config["ui"]["usernamehotspots"]
        utils.NICOTINE = self
        pynicotine.utils.log = self.logMessage

        # self.roomlist = roomlist(self)
        #
        # self.SearchEntry = self.SearchEntryCombo.child
        # self.SearchEntry.connect("activate", self.OnSearch)
        #
        # # for iterating buddy changes to the combos
        # self.CreateRecommendationsWidgets()
        #NicotineInterface

        #gobject.signal_new("network_event", gtk.Window, gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))
        #gobject.signal_new("network_event_lo", gtk.Window, gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))
        #gobject.signal_new("network_event", NicotineInterface, gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,))
        #gobject.signal_new("network_event_lo", NicotineInterface, gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,(gobject.TYPE_PYOBJECT,))

        #self.connect("network_event", self.OnNetworkEvent)
        #self.connect("network_event_lo", self.OnNetworkEvent)

        # if sys.platform.startswith("win"):
        #     self.now_playing1.set_sensitive(False)

        for thing in config["interests"]["likes"]:
            self.likes[thing] = self.likeslist.append([thing])
        for thing in config["interests"]["dislikes"]:
            self.dislikes[thing] = self.dislikeslist.append([thing])

        #self.SetUserStatus(0)
        self.UpdateDownloadFilters()

        log.addlistener(self.logCallback)

        self.isinit = False
        self.chatrooms = self.np.chatrooms
        # self.settingswindow = SettingsWindow(self)
        # self.settingswindow.SettingsWindow.connect("settings-closed", self.OnSettingsClosed)
        # self.fastconfigure = FastConfigureAssistant(self)

        # self.Searches = self.SearchNotebook
        # self.Searches.LoadConfig()
        # self.downloads = Downloads(self)
        # self.uploads = Uploads(self)
        # self.userlist = UserList(self)

        # self.sUserinfoButton.connect("clicked", self.OnGetUserInfo)
        # self.UserInfoCombo.child.connect("activate", self.OnGetUserInfo)
        #
        # self.sPrivateChatButton.connect("clicked", self.OnGetPrivateChat)
        # self.UserPrivateCombo.child.connect("activate", self.OnGetPrivateChat)
        #
        # self.sSharesButton.connect("clicked", self.OnGetShares)
        # self.UserBrowseCombo.child.connect("activate", self.OnGetShares)

        # self.UpdateBandwidth()
        # self.UpdateTransferButtons()
        #
        # # Search Methods
        # self.searchroomslist = {}
        # self.searchmethods = {}
        # self.RoomSearchCombo.set_size_request(150, -1)
        # self.UserSearchCombo.set_size_request(120, -1)
        # self.UserSearchCombo.set_sensitive(False)
        # thread.start_new_thread(self.BuddiesCombosFill, ("",))
        #
        # self.SearchMethod_List.clear()

        # Space after Joined Rooms is important, so it doesn't conflict
        # with any possible real room, but if it's not translated with the space
        # nothing awful will happen
        # self.searchroomslist[_("Joined Rooms ")] = self.RoomSearchCombo_List.append([_("Joined Rooms ")])
        # self.RoomSearchCombo.set_active_iter(self.searchroomslist[_("Joined Rooms ")])
        #
        # for method in [_("Global"), _("Buddies"), _("Rooms"), _("User")]:
        #     self.searchmethods[method] = self.SearchMethod_List.append([method])

        # self.SearchMethod.set_active_iter(self.searchmethods[_("Global")])
        # self.SearchMethod.connect("changed", self.OnSearchMethod)
        # self.UserSearchCombo.hide()
        # self.RoomSearchCombo.hide()
        #
        # ConfigUnset = self.np.config.needConfig()
        # if ConfigUnset:
        #     if ConfigUnset > 1:
        #         self.connect1.set_sensitive(False)
        #         self.rescan1.set_sensitive(True)
        #         # Display FastConfigure
        #         self.OnFastConfigure(None)
        #     else:
        #         # Connect anyway
        #         self.OnFirstConnect(-1)
        # else:
        #     self.OnFirstConnect(-1)


    def AddDebugLevel(self, debugLevel):
        if debugLevel not in self.np.config.sections["logging"]["debugmodes"]:
            self.np.config.sections["logging"]["debugmodes"].append(debugLevel)

    def RemoveDebugLevel(self, debugLevel):
        if debugLevel in self.np.config.sections["logging"]["debugmodes"]:
            self.np.config.sections["logging"]["debugmodes"].remove(debugLevel)

    def OnDebugWarnings(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(1)
        else:
            self.RemoveDebugLevel(1)

    def OnDebugSearches(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(2)
        else:
            self.RemoveDebugLevel(2)

    def OnDebugConnections(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(3)
        else:
            self.RemoveDebugLevel(3)

    def OnDebugMessages(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(4)
        else:
            self.RemoveDebugLevel(4)

    def OnDebugTransfers(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(5)
        else:
            self.RemoveDebugLevel(5)

    def OnSearchMethod(self, widget):

        act = False
        if self.SearchMethod.get_active_text() == _("User"):
            self.UserSearchCombo.show()
            act = True
        else:
            self.UserSearchCombo.hide()

        self.UserSearchCombo.set_sensitive(act)

        act = False
        if self.SearchMethod.get_active_text() == _("Rooms"):
            act = True
            self.RoomSearchCombo.show()
        else:
            self.RoomSearchCombo.hide()

        self.RoomSearchCombo.set_sensitive(act)

    def CreateRecommendationsWidgets(self):

        self.likes = {}
        self.likeslist = gtk.ListStore(gobject.TYPE_STRING)
        self.likeslist.set_sort_column_id(0, gtk.SORT_ASCENDING)

        cols = utils.InitialiseColumns(
            self.LikesList,
            [_("I like") + ":", 0, "text", self.CellDataFunc]
        )

        cols[0].set_sort_column_id(0)
        self.LikesList.set_model(self.likeslist)

        self.RecommendationsList.set_property("rules-hint", True)
        self.RecommendationUsersList.set_property("rules-hint", True)
        self.RecommendationUsersList.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, [('text/plain', 0, 2)], gtk.gdk.ACTION_COPY)
        self.RecommendationUsersList.connect("drag_data_get", self.similar_users_drag_data_get_data)

        self.til_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("#" + _("_Remove this item"), self.OnRemoveThingILike, gtk.STOCK_CANCEL),
            ("#" + _("Re_commendations for this item"), self.OnRecommendItem, gtk.STOCK_INDEX),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch, gtk.STOCK_FIND),
        )

        self.DislikesList.connect("button_press_event", self.OnPopupTIDLMenu)

        self.RecommendationsList.set_model(self.recommendationslist)

        self.r_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("$" + _("I _like this"), self.OnLikeRecommendation),
            ("$" + _("I _don't like this"), self.OnDislikeRecommendation),
            ("#" + _("_Recommendations for this item"), self.OnRecommendRecommendation, gtk.STOCK_INDEX),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch, gtk.STOCK_FIND)
        )

        self.RecommendationsList.connect("button_press_event", self.OnPopupRMenu)
        self.UnrecommendationsList.set_model(self.unrecommendationslist)

        self.ur_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("$" + _("I _like this"), self.OnLikeRecommendation),
            ("$" + _("I _don't like this"), self.OnDislikeRecommendation),
            ("#" + _("_Recommendations for this item"), self.OnRecommendRecommendation, gtk.STOCK_INDEX),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch, gtk.STOCK_FIND)
        )

        self.recommendationusers = {}

        self.RecommendationUsersList.set_model(self.recommendationuserslist)
        self.recommendationuserslist.set_sort_column_id(1, gtk.SORT_ASCENDING)

        self.ru_popup_menu = popup = utils.PopupMenu(self)
        popup.setup(
            ("#" + _("Send _message"), popup.OnSendMessage, gtk.STOCK_EDIT),
            ("", None),
            ("#" + _("Show IP a_ddress"), popup.OnShowIPaddress, gtk.STOCK_NETWORK),
            ("#" + _("Get user i_nfo"), popup.OnGetUserInfo, gtk.STOCK_DIALOG_INFO),
            ("#" + _("Brow_se files"), popup.OnBrowseUser, gtk.STOCK_HARDDISK),
            ("#" + _("Gi_ve privileges"), popup.OnGivePrivileges, gtk.STOCK_JUMP_TO),
            ("", None),
            ("$" + _("_Add user to list"), popup.OnAddToList),
            ("$" + _("_Ban this user"), popup.OnBanUser),
            ("$" + _("_Ignore this user"), popup.OnIgnoreUser)
        )

        self.RecommendationUsersList.connect("button_press_event", self.OnPopupRUMenu)

    def download_large_folder(self, username, folder, files, numfiles, msg):
        FolderDownload(
            self,
            title=_('Nicotine+') + ': Download %(num)i files?' % {'num': numfiles},
            message=_("Are you sure you wish to download %(num)i files from %(user)s's directory %(folder)s?") % {'num': numfiles, 'user': username, 'folder': folder},
            modal=True,
            data=msg,
            callback=self.folder_download_response
        )

    def folder_download_response(self, dialog, response, data):

        if response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return
        elif response == gtk.RESPONSE_OK:
            dialog.destroy()
            self.np.transfers.FolderContentsResponse(data)

    def on_clear_response(self, dialog, response, direction):
        dialog.destroy()

        if response == gtk.RESPONSE_OK:
            if direction == "down":
                self.downloads.ClearTransfers(["Queued"])
            elif direction == "up":
                self.uploads.ClearTransfers(["Queued"])

    def onOpenRoomList(self, dialog, response):
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            self.show_room_list1.set_active(True)

    def OnGetUserInfo(self, widget):
        text = self.UserInfoCombo.child.get_text()
        if not text:
            return
        self.LocalUserInfoRequest(text)
        self.UserInfoCombo.child.set_text("")

    def OnGetShares(self, widget):
        text = self.UserBrowseCombo.child.get_text()
        if not text:
            return
        self.BrowseUser(text)
        self.UserBrowseCombo.child.set_text("")

    def OnLoadFromDisk(self, widget):
        configdir, config = os.path.split(self.np.config.filename)
        sharesdir = os.path.abspath(configdir+os.sep+"usershares"+os.sep)
        try:
            if not os.path.exists(sharesdir):
                os.mkdir(sharesdir)
        except Exception, msg:
            log.addwarning(_("Can't create directory '%(folder)s', reported error: %(error)s") % {'folder': sharesdir, 'error': msg})

        shares = ChooseFile(self.MainWindow.get_toplevel(), sharesdir, multiple=True)
        if shares is None:
            return
        for share in shares:
            try:
                import cPickle as mypickle
                import bz2
                sharefile = bz2.BZ2File(share)
                mylist = mypickle.load(sharefile)
                sharefile.close()
                if not isinstance(mylist, (list, dict)):
                    raise TypeError, "Bad data in file %(sharesdb)s" % {'sharesdb': share}
                username = share.split(os.sep)[-1]
                self.userbrowse.InitWindow(username, None)
                if username in self.userbrowse.users:
                    self.userbrowse.users[username].LoadShares(mylist)
            except Exception, msg:
                log.addwarning(_("Loading Shares from disk failed: %(error)s") % {'error': msg})

    def OnNowPlayingConfigure(self, widget):
        self.now.NowPlaying.show()
        self.now.NowPlaying.deiconify()

    def OnGetPrivateChat(self, widget):
        text = self.UserPrivateCombo.child.get_text()
        if not text:
            return
        self.privatechats.SendMessage(text, None, 1)
        self.UserPrivateCombo.child.set_text("")

    def OnOpenPrivateChat(self, widget, prefix=""):
        # popup
        users = []
        for entry in self.np.config.sections["server"]["userlist"]:
            users.append(entry[0])
        users.sort()
        user = input_box(
            self,
            title=('Nicotine+:') + " " + ("Start Message"),
            message=('Enter the User who you wish to send a private message:'),
            default_text='',
            droplist=users
        )
        if user is not None:
            self.privatechats.SendMessage(user, None, 1)
            self.ChangeMainPage(None, "chatrooms")

    def OnGetAUsersInfo(self, widget, prefix=""):
        # popup
        users = []
        for entry in self.np.config.sections["server"]["userlist"]:
            users.append(entry[0])
        users.sort()
        user = input_box(
            self,
            title=_('Nicotine+: Get User Info'),
            message=_('Enter the User whose User Info you wish to receive:'),
            default_text='',
            droplist=users
        )
        if user is None:
            pass
        else:
            self.LocalUserInfoRequest(user)

    def OnGetAUsersIP(self, widget, prefix=""):
        users = []
        for entry in self.np.config.sections["server"]["userlist"]:
            users.append(entry[0])
        users.sort()
        user = input_box(
            self,
            title=("Nicotine+: Get A User's IP"),
            message=('Enter the User whose IP Address you wish to receive:'),
            default_text='',
            droplist=users
        )
        if user is None:
            pass
        else:
            self.np.queue.put(slskmessages.GetPeerAddress(user))

    def OnGetAUsersShares(self, widget, prefix=""):
        users = []
        for entry in self.np.config.sections["server"]["userlist"]:
            users.append(entry[0])
        users.sort()
        user = input_box(
            self,
            title=("Nicotine+: Get A User's Shares List"),
            message=('Enter the User whose Shares List you wish to receive:'),
            default_text='',
            droplist=users
        )
        if user is None:
            pass
        else:
            self.BrowseUser(user)

    def emit_network_event(self, msgs):
        lo = [msg for msg in msgs if msg.__class__ is slskmessages.FileSearchResult]
        hi = [msg for msg in msgs if msg.__class__ is not slskmessages.FileSearchResult]
        if hi:
            self.emit("network_event", hi)
        if lo:
            self.emit("network_event_lo", lo)
        return False

    # Recieved a network event via emit_network_event
    # with at least one, but possibly more messages
    # call the appropriate event class for these message
    # @param self NicotineFrame (Class)
    # @param widget the main window
    # @param msgs a list of messages
    def OnNetworkEvent(self, widget, msgs):
        for i in msgs:
            if i.__class__ in self.np.events:
                self.np.events[i.__class__](i)
            else:
                self.logMessage("No handler for class %s %s" % (i.__class__, vars(i)))

    def callback(self, msgs):
        self.networkcallback2(msgs)
        #if len(msgs) > 0:
         #   gobject.idle_add(self.emit_network_event, msgs[:])

    def networkcallback2(self, msgs):
        result=None
        #pprint(vars(msgs))

        curtime = time.time()
        for i in msgs[:]:
            #if hasattr(self, "np"):
                #print self.np.users
           # if i.__class__ is not slskmessages.InternalData:
           #     from pprint import pprint
           #     print i
            #    pprint(vars(i))
            if i.__class__  is slskmessages.CantConnectToPeer:
                from pprint import  pprint
                pprint(vars(i))
            if i.__class__ is slskmessages.DownloadFile or i.__class__ is slskmessages.UploadFile:
                self.transfermsgs[i.conn] = i
                msgs.remove(i)
            if i.__class__ is slskmessages.FileSearchResult or i.__class__ is slskmessages.SharedFileList:
                result= self.np.events[i.__class__](i)
            if i.__class__ is slskmessages.ConnClose:
                msgs = self.postTransferMsgs(msgs, curtime)
            if i.__class__ is slskmessages.IncPort:
                self.waitport = i.port
        if curtime - self.transfermsgspostedtime > 1.0:
            msgs = self.postTransferMsgs(msgs, curtime)
        if len(msgs) > 0 and not self.isinit:
            for i in msgs:
                if i.__class__ in self.np.events:
                    self.np.events[i.__class__](i)
                else:
                    self.logMessage("No handler for class %s %s" % (i.__class__, vars(i)))
                if i.__class__ in self.listeners:
                    for listener in self.listeners[i.__class__]:
                        if i.__class__ is slskmessages.FileSearchResult or i.__class__ is slskmessages.SharedFileList:
                            if result:
                                listener(result)
                        else:
                            listener(i)

    def networkcallback(self, msgs):
        self.networkcallback2(msgs)

    # def networkcallback(self, msgs):
    #     curtime = time.time()
    #     for i in msgs[:]:
    #         if i.__class__ is slskmessages.DownloadFile or i.__class__ is slskmessages.UploadFile:
    #             self.transfermsgs[i.conn] = i
    #             msgs.remove(i)
    #         if i.__class__ is slskmessages.ConnClose:
    #             msgs = self.postTransferMsgs(msgs, curtime)
    #     if curtime-self.transfermsgspostedtime > 1.0:
    #         msgs = self.postTransferMsgs(msgs, curtime)
    #     if len(msgs) > 0:
    #         gobject.idle_add(self.emit_network_event, msgs[:])

    def postTransferMsgs(self, msgs, curtime):
        trmsgs = []
        for (key, value) in self.transfermsgs.iteritems():
            trmsgs.append(value)
        msgs = trmsgs+msgs
        self.transfermsgs = {}
        self.transfermsgspostedtime = curtime
        return msgs

    def PopupMessage(self, popup):
        self.logMessage(_(popup.title) + ": " + _(popup.message))

    def logCallback(self, timestamp, level, msg):
        pass
        #self.logMessage(msg)
        #gobject.idle_add(self.updateLog, msg, level, priority=gobject.PRIORITY_DEFAULT)

    def logMessage(self, msg, debugLevel=0):
        #print str(msg)
        log.add(msg, debugLevel)

    def updateLog(self, msg, debugLevel=None):
        '''For information about debug levels see
        pydoc pynicotine.logfacility.logger.add
        '''
        if self.np.config.sections["logging"]["debug"]:
            if debugLevel in (None, 0) or debugLevel in self.np.config.sections["logging"]["debugmodes"]:
                AppendLine(self.LogWindow, msg, self.tag_log, scroll=True)
                if self.np.config.sections["logging"]["logcollapsed"]:
                    self.SetStatusText(msg)
        else:
            if debugLevel in (None, 0, 1):
                try:
                    AppendLine(self.LogWindow, msg, self.tag_log, scroll=True)
                    if self.np.config.sections["logging"]["logcollapsed"]:
                        self.SetStatusText(msg)
                except Exception, e:
                    print e
        return False

    def SetStatusText(self, msg):
        print str(msg)

    def OnDestroy(self, widget):
        self.np.config.sections["privatechat"]["users"] = list(self.privatechats.users.keys())
        self.np.protothread.abort()
        self.np.StopTimers()

        if not self.manualdisconnect:
            self.OnDisconnect(None)

        self.np.config.writeConfig()


        # Closing up all shelves db
        for db in [
            "sharedfiles", "sharedfilesstreams", "wordindex",
            "fileindex", "sharedmtimes",
            "bsharedfiles", "bsharedfilesstreams", "bwordindex",
            "bfileindex", "bsharedmtimes"
        ]:
            self.np.config.sections["transfers"][db].close()

        # Exiting GTK
        #gtk.main_quit()

    def OnFirstConnect(self):

        # Test if we want to do a port mapping
        if self.np.config.sections["server"]["upnp"]:

            # Initialiase a UPnPPortMapping object
            upnp = UPnPPortMapping()

            # Check if we can do a port mapping
            (self.upnppossible, errors) = upnp.IsPossible()

            # Test if we are able to do a port mapping
            if self.upnppossible:
                # Do the port mapping
                thread.start_new_thread(upnp.AddPortMapping, (self, self.np))
            else:
                # Display errors
                if errors is not None:
                    for err in errors:
                        log.addwarning(err)

                # If not we connect without changing anything
                self.OnConnect(-1)
        else:
            # If not we connect without changing anything
            self.OnConnect(-1)

    def connectToServer(self, server, port, login, password, timeout=None):
        self.np.config.sections["server"]["server"]=(server,port)
        self.np.config.sections["server"]["login"], self.np.config.sections["server"]["passw"]=login, password
        self.OnConnect(-1)
        if not self.serverConnectionEvent.wait(timeout):
            raise Exception("Could not connect to the server.")

        msg= self.serverConnectionEvent.msg
        if not msg.success:
            raise Exception(("Can not log in, reason: %s") %(msg.reason))

        return msg

    def getPeerAddress(self, user, timeout=None):
        if user in self.np.users:
            if self.np.users[user].addr:
                return self.np.users[user].addr
        self.np.queue.put(slskmessages.GetPeerAddress(user))
        if not self.getUserAddressEvent.wait(timeout):
            raise Exception("Timeout while requesting peer address.")

        return self.np.users[user].addr

    def createRoom(self, room):
        self.chatrooms.OnPopupCreatePrivateRoom(room)

    def getRoomlist(self, timeout=None):
        self.np.queue.put(slskmessages.RoomList())
        if not self.getRoomlistEvent.wait(timeout):
            raise Exception("Timeout while requesting the room lists from server.")

        return self.chatrooms.roomsctrl.rooms

    def searchFile(self, text, mode=0, users=[], room=None):
        '''
        :param text: The keyword we are searching
        :param mode: 0 for global search, 1 for Room search, 2 for Buddies Search and 3 for user search
        :param users: The list of users we want to narrow the search to
        :param room: A particular room in which we want to search
        :return: a search token to identify this particular search
        '''
        return self.np.search.DoSearch(text, mode, users, room)


    def getJoinedRooms(self):
        return self.chatrooms.roomsctrl.joinedrooms

    def addToSharedFile(self, filename):

        from os import listdir
        from os.path import isfile, join
        filesList=[]
        if isfile(filename):
            filesList.append(filename)
        else:
            filesList = [join(filename, f) for f in listdir(filename) if isfile(join(filename, f))]
        for file in filesList:
            self.np.shares.addToShared(file)

    def getNbConnections(self):
        return self.nbsocket

    def getNbMaxConnection(self):
        return slskproto.MAXFILELIMIT

    def addEventListener(self, event, listener):
        """
        If the user of the API is interested by the rising of a particular type of message, then it will register for
        that event
        :param event: is a message in the slskmessages.py module
        :param listener: is a callback function
        :return: Nothing
        """
        if event in self.listeners:
            self.listeners[event].append(listener)
        else:
            self.listeners[event]=[listener]


    def getSharedFilesList(self, user, timeout=None):
        '''
        Get the shared file list of a given user
        :param user: The user we want to retrieve shared files list
        :param timeout:
        :return:
        '''
        #sharedfilelistresultEvent
        print self.getPeerAddress(user)
        self.np.ProcessRequestToPeer(user, slskmessages.GetSharedFileList(None))
        return user


    def OnConnect(self, widget):

        if self.np.serverconn is not None:
            return

        if widget != -1:
            while not self.np.queue.empty():
                self.np.queue.get(0)

        #self.SetUserStatus(0)
        server = self.np.config.sections["server"]["server"]
        self.np.queue.put(slskmessages.ServerConn(None, server))

        if self.np.servertimer is not None:
            self.np.servertimer.cancel()
            self.np.servertimer = None


    def OnDisconnect(self, event):
        self.disconnect1.set_sensitive(0)
        self.manualdisconnect = 1
        self.np.queue.put(slskmessages.ConnClose(self.np.serverconn))

    def FetchUserListStatus(self):
        for user in self.userlist.userlist:
            self.np.queue.put(slskmessages.AddUser(user[0]))

        return False

    def ConnClose(self, conn, addr):
        self.SetUserStatus(0)

        # self.Searches.interval = 0
        # self.chatrooms.ConnClose()
        # self.privatechats.ConnClose()
        # self.Searches.ConnClose()
        # self.uploads.ConnClose()
        # self.downloads.ConnClose()
        # self.userlist.ConnClose()
        # self.userinfo.ConnClose()
        # self.userbrowse.ConnClose()
        # self.pluginhandler.ServerDisconnectNotification()


    def ConnectError(self, conn):
        if hasattr(self, "uploads"):
            self.uploads.ConnClose()
        if hasattr(self, "downloads"):
            self.downloads.ConnClose()
        # self.pluginhandler.ServerDisconnectNotification()

    def SetUserStatus(self, status):
        """
        set this user'status
        :param status:  1 == Away; 2 == Online
        :return: None
        """
        self.away=status
        self.np.queue.put(slskmessages.SetStatus(self.away))

    def SetSocketStatus(self, status):
        self.nbsocket=status
        #print ("%(current)s/%(limit)s Connections") % {'current': status, 'limit': slskproto.MAXFILELIMIT}
        #self.SocketStatus.pop(self.socket_context_id)
        #self.SocketStatus.push(self.socket_context_id, _("%(current)s/%(limit)s Connections") % {'current': status, 'limit': slskproto.MAXFILELIMIT})

    def InitInterface(self, msg):

        self.uploads.InitInterface(self.np.transfers.uploads)
        self.downloads.InitInterface(self.np.transfers.downloads)
        gobject.idle_add(self.FetchUserListStatus)

        AppendLine(self.LogWindow, self.np.decode(msg.banner), self.tag_log)
        # self.pluginhandler.ServerConnectNotification()
        return self.privatechats, self.chatrooms, self.userinfo, self.userbrowse, self.Searches, self.downloads, self.uploads, self.userlist

    def GetStatusImage(self, status):
        return None
        if status == 1:
            return self.images["away"]
        elif status == 2:
            return self.images["online"]
        else:
            return self.images["offline"]


    def GetUserFlag(self, user):
        if user not in self.flag_users:
            for i in self.np.config.sections["server"]["userlist"]:
                if user == i[0] and i[6] is not None:
                    return i[6]
            return None
        else:
            return self.flag_users[user]


    def OnExit(self, widget):
        self.exiting = 1

    def OnSearch(self, widget):
        self.Searches.OnSearch()

    def OnClearSearchHistory(self, widget):
        self.Searches.OnClearSearchHistory()

    def UpdateBandwidth(self):

        def _calc(l):
            bandwidth = 0.0
            users = 0
            l = [i for i in l if i.conn is not None]
            for i in l:
                if i.speed is not None:
                    bandwidth = bandwidth + i.speed
            return len(l), bandwidth

        def _num_users(l):
            users = []

            for i in l:
                if i.user not in users:
                    users.append(i.user)
            return len(users), len(l)

        if self.np.transfers is not None:
            usersdown, down = _calc(self.np.transfers.downloads)
            usersup, up = _calc(self.np.transfers.uploads)
            total_usersdown, filesdown = _num_users(self.np.transfers.downloads)
            total_usersup, filesup = _num_users(self.np.transfers.uploads)
        else:
            down = up = 0.0
            filesup = filesdown = total_usersdown = total_usersup = usersdown = usersup = 0

        self.DownloadUsers.set_text(_("Users: %s") % total_usersdown)
        self.UploadUsers.set_text(_("Users: %s") % total_usersup)
        self.DownloadFiles.set_text(_("Files: %s") % filesdown)
        self.UploadFiles.set_text(_("Files: %s") % filesup)

        self.DownStatus.pop(self.down_context_id)
        self.UpStatus.pop(self.up_context_id)
        self.DownStatus.push(self.down_context_id, _("Down: %(num)i users, %(speed).1f KB/s") % {'num': usersdown, 'speed': down})
        self.UpStatus.push(self.up_context_id, _("Up: %(num)i users, %(speed).1f KB/s") % {'num': usersup, 'speed': up})

        self.TrayApp.SetToolTip(_("Nicotine+ Transfers: %(speeddown).1f KB/s Down, %(speedup).1f KB/s Up") % {'speeddown': down, 'speedup': up})

    def BanUser(self, user):
        if self.np.transfers is not None:
            self.np.transfers.BanUser(user)

    def UserIpIsBlocked(self, user):
        for ip, username in self.np.config.sections["server"]["ipblocklist"].items():
            if user == username:
                return True
        return False

    def BlockedUserIp(self, user):
        for ip, username in self.np.config.sections["server"]["ipblocklist"].items():
            if user == username:
                return ip
        return None

    def UserIpIsIgnored(self, user):
        for ip, username in self.np.config.sections["server"]["ipignorelist"].items():
            if user == username:
                return True
        return False

    def IgnoredUserIp(self, user):
        for ip, username in self.np.config.sections["server"]["ipignorelist"].items():
            if user == username:
                return ip
        return None

    def IgnoreIP(self, ip):
        if ip is None or ip == "" or ip.count(".") != 3:
            return
        ipignorelist = self.np.config.sections["server"]["ipignorelist"]
        if ip not in ipignorelist:
            ipignorelist[ip] = ""
            self.np.config.writeConfiguration()
            self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)

    def OnIgnoreIP(self, user):
        if user not in self.np.users or type(self.np.users[user].addr) is not tuple:
            if user not in self.np.ipignore_requested:
                self.np.ipignore_requested[user] = 0
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return
        ipignorelist = self.np.config.sections["server"]["ipignorelist"]
        ip, port = self.np.users[user].addr
        if ip not in ipignorelist or self.np.config.sections["server"]["ipignorelist"][ip] != user:
            self.np.config.sections["server"]["ipignorelist"][ip] = user
            self.np.config.writeConfiguration()
            self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)

    def OnUnIgnoreIP(self, user):
        ipignorelist = self.np.config.sections["server"]["ipignorelist"]
        if self.UserIpIsIgnored(user):
            ip = self.IgnoredUserIp(user)
            if ip is not None:
                del ipignorelist[ip]
                self.np.config.writeConfiguration()
                self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)
                return True

        if user not in self.np.users:
            if user not in self.np.ipignore_requested:
                self.np.ipignore_requested[user] = 1
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return

        if not type(self.np.users[user].addr) is tuple:
            return

        ip, port = self.np.users[user].addr
        if ip in ipignorelist:
            del ipignorelist[ip]
            self.np.config.writeConfiguration()
            self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)

    def OnBlockUser(self, user):
        if user not in self.np.users or type(self.np.users[user].addr) is not tuple:
            if user not in self.np.ipblock_requested:
                self.np.ipblock_requested[user] = 0
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return

        ip, port = self.np.users[user].addr
        if ip not in self.np.config.sections["server"]["ipblocklist"] or self.np.config.sections["server"]["ipblocklist"][ip] != user:
            self.np.config.sections["server"]["ipblocklist"][ip] = user
            self.np.config.writeConfiguration()
            self.settingswindow.pages["Ban List"].SetSettings(self.np.config.sections)

    def OnUnBlockUser(self, user):
        if self.UserIpIsBlocked(user):
            ip = self.BlockedUserIp(user)
            if ip is not None:
                del self.np.config.sections["server"]["ipblocklist"][ip]
                self.np.config.writeConfiguration()
                self.settingswindow.pages["Ban List"].SetSettings(self.np.config.sections)
                return True

        if user not in self.np.users:
            if user not in self.np.ipblock_requested:
                self.np.ipblock_requested[user] = 1
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return

        if not type(self.np.users[user].addr) is tuple:
            return

        ip, port = self.np.users[user].addr
        if ip in self.np.config.sections["server"]["ipblocklist"]:
            del self.np.config.sections["server"]["ipblocklist"][ip]
            self.np.config.writeConfiguration()
            self.settingswindow.pages["Ban List"].SetSettings(self.np.config.sections)

    def UnbanUser(self, user):
        if user in self.np.config.sections["server"]["banlist"]:
            self.np.config.sections["server"]["banlist"].remove(user)
            self.np.config.writeConfiguration()

    def IgnoreUser(self, user):
        if user not in self.np.config.sections["server"]["ignorelist"]:
            self.np.config.sections["server"]["ignorelist"].append(user)
            self.np.config.writeConfiguration()

    def UnignoreUser(self, user):
        if user in self.np.config.sections["server"]["ignorelist"]:
            self.np.config.sections["server"]["ignorelist"].remove(user)
            self.np.config.writeConfiguration()

    def BothRescan(self):
        self.OnRescan()
        if self.np.config.sections["transfers"]["enablebuddyshares"]:
            self.OnBuddyRescan()

    def OnRescan(self, widget=None, rebuild=False):
        if self.rescanning:
            return
        self.rescanning = 1

        self.rescan1.set_sensitive(False)
        self.rebuild1.set_sensitive(False)
        self.logMessage(("Rescanning started"))

        shared = self.np.config.sections["transfers"]["shared"][:]
        if self.np.config.sections["transfers"]["sharedownloaddir"]:
            shared.append((('Downloaded'), self.np.config.sections["transfers"]["downloaddir"]))

        cleanedshares = []
        for combo in shared:
            if combo not in cleanedshares:
                cleanedshares.append(combo)
        msg = slskmessages.RescanShares(cleanedshares, lambda: None)
        thread.start_new_thread(self.np.shares.RescanShares, (msg, rebuild))

    def OnRebuild(self, widget=None):
        self.OnRescan(widget, rebuild=True)

    def OnBuddyRescan(self, widget=None, rebuild=False):
        if self.brescanning:
            return
        self.brescanning = 1

        self.rescan_buddy.set_sensitive(False)
        self.rebuild_buddy.set_sensitive(False)
        self.logMessage(("Rescanning Buddy Shares started"))

        shared = self.np.config.sections["transfers"]["buddyshared"][:] + self.np.config.sections["transfers"]["shared"][:]
        if self.np.config.sections["transfers"]["sharedownloaddir"]:
            shared.append((('Downloaded'), self.np.config.sections["transfers"]["downloaddir"]))

        cleanedshares = []
        for i in shared:
            if i not in cleanedshares:
                cleanedshares.append(i)
        msg = slskmessages.RescanBuddyShares(cleanedshares, lambda: None)
        thread.start_new_thread(self.np.shares.RescanBuddyShares, (msg, rebuild))

    def OnBuddyRebuild(self, widget=None):
        self.OnBuddyRescan(widget, rebuild=True)

    def _BuddyRescanFinished(self, data):
        self.np.config.setBuddyShares(*data)
        self.np.config.writeShares()

        self.rescan_buddy.set_sensitive(True)
        self.rebuild_buddy.set_sensitive(True)
        if self.np.transfers is not None:
            self.np.shares.sendNumSharedFoldersFiles()
        self.brescanning = 0
        self.logMessage(("Rescanning Buddy Shares finished"))
        self.BuddySharesProgress.hide()
        self.np.shares.CompressShares("buddy")

    def _RescanFinished(self, data):
        self.np.config.setShares(*data)
        self.np.config.writeShares()

        self.rescan1.set_sensitive(True)
        self.rebuild1.set_sensitive(True)
        if self.np.transfers is not None:
            self.np.shares.sendNumSharedFoldersFiles()
        self.rescanning = 0
        self.logMessage(_("Rescanning finished"))
        self.SharesProgress.hide()
        self.np.shares.CompressShares("normal")

    def RescanFinished(self, data, type):
        if type == "buddy":
            gobject.idle_add(self._BuddyRescanFinished, data)
        elif type == "normal":
            gobject.idle_add(self._RescanFinished, data)

    def OnSettingsShares(self, widget):
        self.OnSettings(widget, 'Shares')

    def OnSettingsSearches(self, widget):
        self.OnSettings(widget, 'Searches')

    def OnSettingsDownloads(self, widget):
        self.OnSettings(widget, 'Downloads')
        self.settingswindow.pages["Downloads"].DownloadFilters.set_expanded(True)

    def OnSettingsUploads(self, widget):
        self.OnSettings(widget, 'Transfers')
        self.settingswindow.pages["Transfers"].Uploads.set_expanded(True)

    def OnSettingsUserinfo(self, widget):
        self.OnSettings(widget, 'User info')

    def OnSettingsLogging(self, widget):
        self.OnSettings(widget, 'Logging')

    def OnSettingsIgnore(self, widget):
        self.OnSettings(widget, 'Ingore List')

    def OnSettingsBanIgnore(self, widget):
        self.OnSettings(widget, 'Ban List')

    def OnFastConfigure(self, widget):
        if not self.settingswindow.SettingsWindow.get_property("visible"):
            self.fastconfigure.show()

    def OnSettings(self, widget, page=None):
        if not self.fastconfigure.window.get_property("visible"):
            self.settingswindow.SetSettings(self.np.config.sections)
            if page:
                self.settingswindow.SwitchToPage(page)
            self.settingswindow.SettingsWindow.show()
            self.settingswindow.SettingsWindow.deiconify()

    def OnSettingsClosed(self, widget, msg):
        if msg == "cancel":
            self.settingswindow.SettingsWindow.hide()
            return
        output = self.settingswindow.GetSettings()
        if type(output) is not tuple:
            return
        if msg == "ok":
            self.settingswindow.SettingsWindow.hide()
        needrescan, needcolors, needcompletion, config = output
        for (key, data) in config.items():
            self.np.config.sections[key].update(data)
        config = self.np.config.sections
        # Write utils.py options
        utils.DECIMALSEP = config["ui"]["decimalsep"]
        utils.CATCH_URLS = config["urls"]["urlcatching"]
        utils.HUMANIZE_URLS = config["urls"]["humanizeurls"]
        utils.PROTOCOL_HANDLERS = config["urls"]["protocols"].copy()
        utils.PROTOCOL_HANDLERS["slsk"] = self.OnSoulSeek
        utils.USERNAMEHOTSPOTS = config["ui"]["usernamehotspots"]
        uselimit = config["transfers"]["uselimit"]
        uploadlimit = config["transfers"]["uploadlimit"]
        limitby = config["transfers"]["limitby"]

        if config["transfers"]["geoblock"]:
            panic = config["transfers"]["geopanic"]
            cc = config["transfers"]["geoblockcc"]
            self.np.queue.put(slskmessages.SetGeoBlock([panic, cc]))
        else:
            self.np.queue.put(slskmessages.SetGeoBlock(None))

        self.np.queue.put(slskmessages.SetUploadLimit(uselimit, uploadlimit, limitby))
        self.np.queue.put(slskmessages.SetDownloadLimit(config["transfers"]["downloadlimit"]))
        self.np.ToggleRespondDistributed(None, settings=True)

        # Modify GUI
        self.UpdateDownloadFilters()
        self.np.config.writeConfiguration()

        if self.np.transfers is not None:
            self.np.transfers.checkUploadQueue()
        self.UpdateTransferButtons()
        if needrescan:
            self.needrescan = 1

        if msg == "ok" and self.needrescan:
            self.needrescan = 0
            self.BothRescan()

        ConfigUnset = self.np.config.needConfig()
        if ConfigUnset > 1:
            if self.np.transfers is not None:
                self.connect1.set_sensitive(0)
            # self.OnSettings(None)
            self.OnFastConfigure(None)
        else:
            if self.np.transfers is None:
                self.connect1.set_sensitive(1)
        # self.SetAllToolTips()
        #self.pluginhandler.check_enabled()

    def OnChangePassword(self, password):
        self.np.queue.put(slskmessages.ChangePassword(password))

    def OnBackupConfig(self, widget=None):
        response = SaveFile(
            self.MainWindow.get_toplevel(),
            os.path.dirname(self.np.config.filename),
            title="Pick a filename for config backup, or cancel to use a timestamp"
        )
        if response:
            error, message = self.np.config.writeConfigBackup(response[0])
        else:
            error, message = self.np.config.writeConfigBackup()
        if error:
            self.logMessage("Error backing up config: %s" % message)
        else:
            self.logMessage("Config backed up to: %s" % message)


    def UpdateDownloadFilters(self):
        proccessedfilters = []
        outfilter = "(\\\\("
        failed = {}
        df = self.np.config.sections["transfers"]["downloadfilters"]
        df.sort()
        # Get Filters from config file and check their escaped status
        # Test if they are valid regular expressions and save error messages

        for item in df:
            filter, escaped = item
            if escaped:
                dfilter = re.escape(filter)
                dfilter = dfilter.replace("\*", ".*")
            else:
                dfilter = filter
            try:
                re.compile("("+dfilter+")")
                outfilter += dfilter
                proccessedfilters.append(dfilter)
            except Exception, e:
                failed[dfilter] = e

            proccessedfilters.append(dfilter)

            if item is not df[-1]:
                outfilter += "|"

        # Crop trailing pipes
        while outfilter[-1] == "|":
            outfilter = outfilter[:-1]

        outfilter += ")$)"
        try:
            re.compile(outfilter)
            self.np.config.sections["transfers"]["downloadregexp"] = outfilter
            # Send error messages for each failed filter to log window
            if len(failed.keys()) >= 1:
                errors = ""
                for filter, error in failed.items():
                    errors += "Filter: %s Error: %s " % (filter, error)
                error = ("Error: %(num)d Download filters failed! %(error)s " % {'num': len(failed.keys()), 'error': errors})
                self.logMessage(error)
        except Exception, e:
            # Strange that individual filters _and_ the composite filter both fail
            self.logMessage(("Error: Download Filter failed! Verify your filters. Reason: %s" % e))
            self.np.config.sections["transfers"]["downloadregexp"] = ""

    def UpdateTransferButtons(self):
        if self.np.config.sections["transfers"]["enabletransferbuttons"]:
            self.DownloadButtons.show()
            self.UploadButtons.show()
        else:
            self.UploadButtons.hide()
            self.DownloadButtons.hide()



    def OnShowFlags(self, widget):
        if self.chatrooms is None:
            return
        show = widget.get_active()
        self.np.config.sections["columns"]["hideflags"] = (not show)
        for room in self.chatrooms.roomsctrl.joinedrooms:
            self.chatrooms.roomsctrl.joinedrooms[room].cols[1].set_visible(show)
            self.np.config.sections["columns"]["chatrooms"][room][1] = int(show)
        self.userlist.cols[1].set_visible(show)
        self.np.config.sections["columns"]["userlist"][1] = int(show)
        self.np.config.writeConfiguration()


    def OnCheckPrivileges(self, widget):
        self.np.queue.put(slskmessages.CheckPrivileges())

    def OnSoulSeek(self, url):
        try:
            user, file = urllib.url2pathname(url[7:]).split("/", 1)
            if file[-1] == "/":
                self.np.ProcessRequestToPeer(user, slskmessages.FolderContentsRequest(None, file[:-1].replace("/", "\\")))
            else:
                self.np.transfers.getFile(user, file.replace("/", "\\"), "")
        except:
            self.logMessage(_("Invalid SoulSeek meta-url: %s") % url)

    def LocalUserInfoRequest(self, user):
        # Hack for local userinfo requests, for extra security
        if user == self.np.config.sections["server"]["login"]:
            try:
                if self.np.config.sections["userinfo"]["pic"] != "":
                    if sys.platform == "win32":
                        userpic = u"%s" % self.np.config.sections["userinfo"]["pic"]
                    else:
                        userpic = self.np.config.sections["userinfo"]["pic"]
                    if os.path.exists(userpic):
                        has_pic = True
                        f = open(userpic, 'rb')
                        pic = f.read()
                        f.close()
                    else:
                        has_pic = False
                        pic = None
                else:
                    has_pic = False
                    pic = None
            except:
                pic = None

            descr = self.np.encode(eval(self.np.config.sections["userinfo"]["descr"], {}))

            if self.np.transfers is not None:

                totalupl = self.np.transfers.getTotalUploadsAllowed()
                queuesize = self.np.transfers.getUploadQueueSizes()[0]
                slotsavail = self.np.transfers.allowNewUploads()
                ua = self.np.config.sections["transfers"]["remotedownloads"]
                if ua:
                    uploadallowed = self.np.config.sections["transfers"]["uploadallowed"]
                else:
                    uploadallowed = ua
                self.userinfo.ShowLocalInfo(user, descr, has_pic, pic, totalupl, queuesize, slotsavail, uploadallowed)

        else:
            self.np.ProcessRequestToPeer(user, slskmessages.UserInfoRequest(None), self.userinfo)

    # Here we go, ugly hack for getting your own shares
    def BrowseUser(self, user):
        login = self.np.config.sections["server"]["login"]
        if user is None or user == login:
            user = login
            if user in [i[0] for i in self.np.config.sections["server"]["userlist"]] and self.np.config.sections["transfers"]["enablebuddyshares"]:
                m = slskmessages.SharedFileList(None, self.np.config.sections["transfers"]["bsharedfilesstreams"])
            else:
                m = slskmessages.SharedFileList(None, self.np.config.sections["transfers"]["sharedfilesstreams"])
            m.parseNetworkMessage(m.makeNetworkMessage(nozlib=1), nozlib=1)
            self.userbrowse.ShowInfo(login, m)
        else:
            self.np.ProcessRequestToPeer(user, slskmessages.GetSharedFileList(None), self.userbrowse)

    def OnBrowseMyShares(self, widget):
        self.BrowseUser(None)

    def PrivateRoomRemoveUser(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomRemoveUser(room, user))

    def PrivateRoomAddUser(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomAddUser(room, user))

    def PrivateRoomAddOperator(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomAddOperator(room, user))

    def PrivateRoomRemoveOperator(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomRemoveOperator(room, user))

    def OnPopupLogMenu(self, widget, event):
        if event.button != 3:
            return False
        widget.emit_stop_by_name("button-press-event")
        self.logpopupmenu.popup(None, None, None, event.button, event.time)
        return True

    #
    # Everything related to the log window
    #
    def OnFindLogWindow(self, widget):
        self.OnFindTextview(None, self.LogWindow)

    def OnCopyLogWindow(self, widget):
        bound = self.LogWindow.get_buffer().get_selection_bounds()
        if bound is not None and len(bound) == 2:
            start, end = bound
            log = self.LogWindow.get_buffer().get_text(start, end)
            self.clip.set_text(log)

    def OnCopyAllLogWindow(self, widget):
        start, end = self.LogWindow.get_buffer().get_bounds()
        log = self.LogWindow.get_buffer().get_text(start, end)
        self.clip.set_text(log)

    def OnClearLogWindow(self, widget):
        self.LogWindow.get_buffer().set_text("")

    #
    # Finding text in a text view
    # Used in private msg, chatrooms and log window
    #
    def OnFindTextview(self, widget, textview, repeat=False):

        if "FindDialog" not in self.__dict__:
            self.FindDialog = FindDialog(
                self,
                ('Enter the string to search for:'),
                "",
                textview=textview,
                modal=False
            )
            self.FindDialog.set_title(_('Nicotine+: Find string'))
            self.FindDialog.set_icon(self.images["n"])
            self.FindDialog.set_default_size(300, 100)
            self.FindDialog.set_transient_for(self.MainWindow)
            self.FindDialog.show()
            self.FindDialog.connect("find-click", self.OnFindClicked)
            return

        if textview is not self.FindDialog.textview:
            repeat = False

        self.FindDialog.textview = textview
        self.FindDialog.currentPosition = None
        self.FindDialog.nextPosition = None

        self.FindDialog.set_transient_for(self.MainWindow)
        self.FindDialog.show()
        self.FindDialog.deiconify()

        if repeat:
            self.OnFindClicked(widget, self.FindDialog.lastdirection)
        else:
            self.FindDialog.entry.set_text("")

    def OnFindClicked(self, widget, direction):

        if self.FindDialog.textview is None:
            return

        self.FindDialog.lastdirection = direction
        textview = self.FindDialog.textview
        buffer = textview.get_buffer()
        start, end = buffer.get_bounds()
        query = self.FindDialog.entry.get_text()

        textview.emit("select-all", False)

        if self.FindDialog.currentPosition is None:
            self.FindDialog.currentPosition = buffer.create_mark(None, start, False)
            self.FindDialog.nextPosition = buffer.create_mark(None, start, False)

        second = 0

        if direction == "next":
            current = buffer.get_mark("insert")
            iter = buffer.get_iter_at_mark(current)
            match1 = iter.forward_search(query, gtk.TEXT_SEARCH_TEXT_ONLY, limit=None)

            if match1 is not None and len(match1) == 2:
                match_start, match_end = match1
                buffer.place_cursor(match_end)
                buffer.select_range(match_end, match_start)
                textview.scroll_to_iter(match_start, 0)
            else:
                iter = start
                match1 = iter.forward_search(query, gtk.TEXT_SEARCH_TEXT_ONLY, limit=None)

                if match1 is not None and len(match1) == 2:
                    match_start, match_end = match1
                    buffer.place_cursor(match_end)
                    buffer.select_range(match_end, match_start)
                    textview.scroll_to_iter(match_start, 0)

        elif direction == "previous":

            current = buffer.get_mark("insert")
            iter = buffer.get_iter_at_mark(current)
            match1 = iter.backward_search(query, gtk.TEXT_SEARCH_TEXT_ONLY, limit=None)

            if match1 is not None and len(match1) == 2:
                match_start, match_end = match1
                buffer.place_cursor(match_start)
                buffer.select_range(match_start, match_end)
                textview.scroll_to_iter(match_start, 0)
            return

    def OnAddThingILike(self, widget):
        thing = utils.InputDialog(self.MainWindow, _("Add thing I like"), _("I like") + ":")
        if thing and thing.lower() not in self.np.config.sections["interests"]["likes"]:
            thing = thing.lower()
            self.np.config.sections["interests"]["likes"].append(thing)
            self.likes[thing] = self.likeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingILike(self.np.encode(thing)))

    def OnAddThingIDislike(self, widget):
        thing = utils.InputDialog(self.MainWindow, _("Add thing I don't like"), _("I don't like") + ":")
        if thing and thing.lower() not in self.np.config.sections["interests"]["dislikes"]:
            thing = thing.lower()
            self.np.config.sections["interests"]["dislikes"].append(thing)
            self.dislikes[thing] = self.dislikeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingIHate(self.np.encode(thing)))

    def SetRecommendations(self, title, recom):
        self.recommendationslist.clear()
        for (thing, rating) in recom.iteritems():
            thing = self.np.decode(thing)
            self.recommendationslist.append([thing, Humanize(rating), rating])
        self.recommendationslist.set_sort_column_id(2, gtk.SORT_DESCENDING)

    def SetUnrecommendations(self, title, recom):
        self.unrecommendationslist.clear()
        for (thing, rating) in recom.iteritems():
            thing = self.np.decode(thing)
            self.unrecommendationslist.append([thing, Humanize(rating), rating])
        self.unrecommendationslist.set_sort_column_id(2, gtk.SORT_ASCENDING)

    def GlobalRecommendations(self, msg):
        self.SetRecommendations("Global recommendations", msg.recommendations)
        self.SetUnrecommendations("Unrecommendations", msg.unrecommendations)

    def Recommendations(self, msg):
        self.SetRecommendations("Recommendations", msg.recommendations)
        self.SetUnrecommendations("Unrecommendations", msg.unrecommendations)

    def ItemRecommendations(self, msg):
        self.SetRecommendations(_("Recommendations for %s") % msg.thing, msg.recommendations)
        self.SetUnrecommendations("Unrecommendations", msg.unrecommendations)

    def OnGlobalRecommendationsClicked(self, widget):
        self.np.queue.put(slskmessages.GlobalRecommendations())

    def OnRecommendationsClicked(self, widget):
        self.np.queue.put(slskmessages.Recommendations())

    def OnSimilarUsersClicked(self, widget):
        self.np.queue.put(slskmessages.SimilarUsers())

    def SimilarUsers(self, msg):
        self.recommendationuserslist.clear()
        self.recommendationusers = {}
        for user in msg.users.keys():
            iter = self.recommendationuserslist.append([self.images["offline"], user, "0", "0", 0, 0, 0])
            self.recommendationusers[user] = iter
            self.np.queue.put(slskmessages.AddUser(user))

    def ItemSimilarUsers(self, msg):
        #self.recommendationuserslist.clear()
        self.recommendationusers = {}
        for user in msg.users:
            iter = self.recommendationuserslist.append([self.images["offline"], user, "0", "0", 0, 0, 0])
            self.recommendationusers[user] = iter
            self.np.queue.put(slskmessages.AddUser(user))

    def GetUserStatus(self, msg):
        if msg.user not in self.recommendationusers:
            return
        img = self.GetStatusImage(msg.status)
        self.recommendationuserslist.set(self.recommendationusers[msg.user], 0, img, 4, msg.status)

    def GetUserStats(self, msg):
        from pprint import pprint

        # return None
        # if msg.user not in self.recommendationusers:
        #     return
        if not self.stats:
            self.stats={}
        self.stats[msg.user]= {"avgspeed":msg.avgspeed, "nbfiles":msg.files}
        print self.stats

    def OnRemoveThingILike(self, widget):
        thing = self.til_popup_menu.get_user()
        if thing not in self.np.config.sections["interests"]["likes"]:
            return
        self.likeslist.remove(self.likes[thing])
        del self.likes[thing]
        self.np.config.sections["interests"]["likes"].remove(thing)
        self.np.config.writeConfiguration()
        self.np.queue.put(slskmessages.RemoveThingILike(self.np.encode(thing)))

    def OnRecommendItem(self, widget):
        thing = self.til_popup_menu.get_user()
        self.np.queue.put(slskmessages.ItemRecommendations(self.np.encode(thing)))
        self.np.queue.put(slskmessages.ItemSimilarUsers(self.np.encode(thing)))

    def OnRemoveThingIDislike(self, widget):
        thing = self.tidl_popup_menu.get_user()
        if thing not in self.np.config.sections["interests"]["dislikes"]:
            return
        self.dislikeslist.remove(self.dislikes[thing])
        del self.dislikes[thing]
        self.np.config.sections["interests"]["dislikes"].remove(thing)
        self.np.config.writeConfiguration()
        self.np.queue.put(slskmessages.RemoveThingIHate(self.np.encode(thing)))

    def OnLikeRecommendation(self, widget):
        thing = widget.parent.get_user()
        if widget.get_active() and thing not in self.np.config.sections["interests"]["likes"]:
            self.np.config.sections["interests"]["likes"].append(thing)
            self.likes[thing] = self.likeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingILike(self.np.encode(thing)))
        elif not widget.get_active() and thing in self.np.config.sections["interests"]["likes"]:
            self.likeslist.remove(self.likes[thing])
            del self.likes[thing]
            self.np.config.sections["interests"]["likes"].remove(thing)
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.RemoveThingILike(self.np.encode(thing)))

    def OnDislikeRecommendation(self, widget):
        thing = widget.parent.get_user()
        if widget.get_active() and thing not in self.np.config.sections["interests"]["dislikes"]:
            self.np.config.sections["interests"]["dislikes"].append(thing)
            self.dislikes[thing] = self.dislikeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingIHate(self.np.encode(thing)))
        elif not widget.get_active() and thing in self.np.config.sections["interests"]["dislikes"]:
            self.dislikeslist.remove(self.dislikes[thing])
            del self.dislikes[thing]
            self.np.config.sections["interests"]["dislikes"].remove(thing)
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.RemoveThingIHate(self.np.encode(thing)))

    def OnRecommendRecommendation(self, widget):
        thing = self.r_popup_menu.get_user()
        self.np.queue.put(slskmessages.ItemRecommendations(self.np.encode(thing)))
        self.np.queue.put(slskmessages.ItemSimilarUsers(self.np.encode(thing)))

    def OnRecommendSearch(self, widget):
        thing = widget.parent.get_user()
        self.SearchEntry.set_text(thing)
        self.ChangeMainPage(None, "search")

    def OnPopupRMenu(self, widget, event):
        if event.button != 3:
            return
        d = self.RecommendationsList.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return
        path, column, x, y = d
        iter = self.recommendationslist.get_iter(path)
        thing = self.recommendationslist.get_value(iter, 0)
        items = self.r_popup_menu.get_children()
        self.r_popup_menu.set_user(thing)
        items[0].set_active(thing in self.np.config.sections["interests"]["likes"])
        items[1].set_active(thing in self.np.config.sections["interests"]["dislikes"])
        self.r_popup_menu.popup(None, None, None, event.button, event.time)


    def OnShowTickers(self, widget):
        if not self.chatrooms:
            return
        show = widget.get_active()
        self.np.config.sections["ticker"]["hide"] = (not show)
        self.np.config.writeConfiguration()
        for room in self.chatrooms.roomsctrl.joinedrooms.values():
            room.ShowTicker(show)

    def RecommendationsExpanderStatus(self, widget):
        if widget.get_property("expanded"):
            self.RecommendationsVbox.set_child_packing(widget, False, True, 0, 0)
        else:
            self.RecommendationsVbox.set_child_packing(widget, True, True, 0, 0)

    def GivePrivileges(self, user, days):
        self.np.queue.put(slskmessages.GivePrivileges(user, days))


class TrayApp:

    def CreateMenu(self):

        try:

            self.tray_popup_menu_server = popup0 = PopupMenu(self)

            popup0.setup(
                ("#" + _("Disconnect"), self.frame.OnDisconnect, gtk.STOCK_DISCONNECT)
            )

            self.tray_popup_menu = popup = PopupMenu(self)

            popup.setup(
                ("#" + ("Hide / Show Nicotine+"), self.HideUnhideWindow, gtk.STOCK_GOTO_BOTTOM),
                (1, ("Server"), self.tray_popup_menu_server, self.OnPopupServer),
                ("#" + ("Settings"), self.frame.OnSettings, gtk.STOCK_PREFERENCES),
                ("#" + ("Send Message"), self.frame.OnOpenPrivateChat, gtk.STOCK_EDIT),
                ("#" + ("Lookup a User's IP"), self.frame.OnGetAUsersIP, gtk.STOCK_NETWORK),
                ("#" + ("Lookup a User's Info"), self.frame.OnGetAUsersInfo, gtk.STOCK_DIALOG_INFO),
                ("#" + ("Lookup a User's Shares"), self.frame.OnGetAUsersShares, gtk.STOCK_HARDDISK),
                ("#" + ("Quit"), self.frame.OnExit, gtk.STOCK_QUIT)
            )

        except Exception as e:
            log.addwarning(('ERROR: tray menu, %(error)s') % {'error': e})


class gstreamer:
    def __init__(self):
        self.player = None
        try:
            import pygst
            pygst.require("0.10")
            import gst
        except Exception, error:
            return
        self.gst = gst
        try:
            self.player = gst.element_factory_make("playbin", "player")
            fakesink = gst.element_factory_make('fakesink', "my-fakesink")
            self.player.set_property("video-sink", fakesink)
        except Exception, error:
            log.addwarning(("ERROR: Gstreamer-python could not play: %(error)s") % {'error': error})
            self.gst = self.player = None
            return

        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self.on_gst_message)

    def play(self, path):
        self.player.set_property('uri', "file://" + path)
        self.player.set_state(self.gst.STATE_PLAYING)

    def on_gst_message(self, bus, message):
        t = message.type
        if t == self.gst.MESSAGE_EOS:
            self.player.set_state(self.gst.STATE_NULL)
        elif t == self.gst.MESSAGE_ERROR:
            self.player.set_state(self.gst.STATE_NULL)


