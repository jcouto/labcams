from .utils import *

class BasePlugin():
    def __init__(self,gui,name):
        self.gui = gui
        self.name = name
    def update(self):
        pass
    
    def parse_command(self,msg):
        cmd,msg = msg.split(':')
        self._parse_command(cmd,msg)
        
    def _parse_command(self,command,msg):
        pass
plugins = []

def load_plugins(config = None):
    if len(plugins):
        return
    pref = getPreferences(preffile = config)
    if not 'plugins_folder' in pref.keys():
        pref['plugins_folder'] = pjoin(os.path.expanduser('~'),
                                       'labcams','plugins')
    if not os.path.exists(pref['plugins_folder']):
        os.makedirs(pref['plugins_folder'])
    pfolders = glob(pjoin(pref['plugins_folder'],'*'))
    pfolders = list(filter(os.path.isdir,pfolders))
    for f in pfolders:
        plugins.append(dict(name = os.path.basename(f),
                            path = f,
                            plugin = None))
    import sys
    sys.path.append(pref['plugins_folder'])
    for f in plugins:
        eval('exec("from {0} import {0}")'.format(
            f['name']))
        f['plugin'] = eval("{0}".format(f['name']))
    return plugins
