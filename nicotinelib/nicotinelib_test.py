
import os
import platform
import sys
from pynicotine.api.nicotineapi import  nicotineapi, roomlist
from pprint import pprint
from pynicotine import slskmessages


def printResults(msg):
    pprint(vars(msg))

def onFileSearchResult(results):
    print "Search result"
    print results

def onSharedFileResult(results):
    print "Shared File result"
    print results

config = os.path.join(os.path.expanduser("~"), '.nicotine', 'config')
plugins = os.path.join(os.path.expanduser("~"), '.nicotine', 'plugins')

#conn= NicotineConnection(config)


api= nicotineapi(config, None) #c= conn.connectToServer("server.slsknet.org", 2242, 2.0)
#interface.connect("network_event", interface.OnNetworkEvent)
#interface.connect("network_event_lo", interface.OnNetworkEvent)

api.addEventListener(slskmessages.GetSharedFileList, printResults)
api.addEventListener(slskmessages.FileSearchRequest, printResults) # FilesearchRequest= entre pairs
#api.addEventListener(slskmessages.FileRequest, printResults)
api.addEventListener(slskmessages.FileSearch, printResults) # FileSearch = entre client et serveur
api.addEventListener(slskmessages.MessageUser, printResults)
api.addEventListener(slskmessages.SharedFileList, onSharedFileResult)
api.addEventListener(slskmessages.FileSearchResult, onFileSearchResult) # Lorsque le resultat d'une recherche est disponible


msg= api.connectToServer("server.slsknet.org", 2242, "rostykamga", "00001988")

#pprint (vars(msg))

#roomlist= api.getRoomlist()

#print "now printing the roomlist"
#print(roomlist)
#pprint(roomlist)
#print "finished printing roomlist"

#print "getting shared files of a user"
#files= api.getSharedFilesList("cykros")
#print "got result, printing shared files"
#print files
api.addToSharedFile("/home/rostand/Musique")
print api.getPeerAddress("rostykamga")
api.SetUserStatus(2)
#print api.getPeerAddress("rtkamga")
#print "now sharing a file"

#keyword= "talla andre"
#print "searching for %s"%keyword
#token= api.searchFile(keyword)
#print "token returned %d"%token
