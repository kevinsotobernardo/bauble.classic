#
# prefs.py
#

import sys, os
import gtk
import bauble
import bauble.utils as utils
import bauble.paths as paths
from bauble.utils.log import debug, warning

# TODO: include the version of the database in the prefs so that if the prefs
# are opened with a different version then the user will know and possible
# migrate pref version though i don't think the prefs  format will change much

# TODO: make sure the version numbers are compatible,
# if we are upgrading to a new version we should copy the old
# config somewhere else, copy any relevant keys and set the config
# version in the new file

# TODO: should also possibly check that the config version and
# database versions match up

# TODO: maybe we should have a create method that creates the preferences
# todo a one time thing if the files doesn't exist

default_filename = 'config'
default_prefs_file = os.path.join(paths.user_dir(), default_filename)

prefs_icon_dir = os.path.join(paths.lib_dir(), 'images')
general_prefs_icon = os.path.join(prefs_icon_dir, 'prefs_general.png')
security_prefs_icon = os.path.join(prefs_icon_dir, 'prefs_security.png')

config_version_pref = 'bauble.config.version'
config_version = bauble.version[0], bauble.version[1] 

## class PreferencesMgr(gtk.Dialog):
    
##     def __init__(self):
##         gtk.Dialog.__init__(self, "Preferences", None,
##                    gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
##                    (gtk.STOCK_OK, gtk.RESPONSE_OK,
##                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
##         self.current_frame = None
##         self.create_gui()


##     def create_gui(self):
##         model = gtk.ListStore(str, gtk.gdk.Pixbuf)
        
##         #pixbuf = gtk.gdk.pixbuf_new_from_file("images/prefs_general.png")
##         pixbuf = gtk.gdk.pixbuf_new_from_file(general_prefs_icon)
##         model.append(["General", pixbuf])
        
##         #pixbuf = gtk.gdk.pixbuf_new_from_file("images/prefs_security.png")
##         pixbuf = gtk.gdk.pixbuf_new_from_file(security_prefs_icon)
##         model.append(["Security", pixbuf])
        
##         self.icon_view = gtk.IconView(model)
##         self.icon_view.set_text_column(0)
##         self.icon_view.set_pixbuf_column(1)
##         self.icon_view.set_orientation(gtk.ORIENTATION_VERTICAL)
##         self.icon_view.set_selection_mode(gtk.SELECTION_SINGLE)
##         self.icon_view.connect("selection-changed", self.on_select, model)
##         self.icon_view.set_columns(1) # this isn't in the pygtk docs
##         self.icon_view.set_item_width(-1)
##         self.icon_view.set_size_request(72, -1)
        
##         self.content_box = gtk.HBox(False)
##         self.content_box.pack_start(self.icon_view, fill=True, expand=False)
##         self.icon_view.select_path((0,)) # select a category, will create frame
##         self.show_all()
##         self.vbox.pack_start(self.content_box)        
##         self.resize(640, 480)
##         self.show_all()


##     def on_select(self, icon_view, model=None):
##         selected = icon_view.get_selected_items()
##         if len(selected) == 0: return
##         i = selected[0][0]
##         category = model[i][0]
##         if self.current_frame is not None:
##             self.content_box.remove(self.current_frame)
##             self.current_frame.destroy()
##             self.current_frame = None
##         if category == "General":
##             self.current_frame = self.create_general_frame()
##         elif category == "Security":
##             self.current_frame = self.create_security_frame()    
##         self.content_box.pack_end(self.current_frame, fill=True, expand=True)
##         self.show_all()
        
        
##     def create_general_frame(self):
##         frame = gtk.Frame("General")
##         box = gtk.VBox(False)
##         box.pack_start(gtk.Label("Nothing to see here. Move on."))
##         frame.add(box)
##         return frame        


##     def create_security_frame(self):
##         frame = gtk.Frame("Security")        
##         box = gtk.VBox(False)
##         box.pack_start(gtk.Label("Nothing to see here. Move on."))
##         frame.add(box)
##         return frame        


from ConfigParser import ConfigParser

class _prefs(dict):
    
    def __init__(self, filename=default_prefs_file):
        self._filename = filename
    

    def init(self):
        '''
        initialize the preferences, should only be called from app.main
        '''
        # create directory tree of filename if it doesn't yet exist
        head, tail = os.path.split(self._filename)
        if not os.path.exists(head):
            os.makedirs(head)
            
        self.config = ConfigParser()

        # set the version if the file doesn't exist
        
        if not os.path.exists(self._filename):
            debug('path doesn\'t exists')
            self[config_version_pref] = config_version
        else:
            debug('reading %s' % self._filename)
            self.config.read(self._filename)
        version = self[config_version_pref]
        if version is None:
            warning('%s has no config version pref' % self._filename)
            warning('seting the config version to %s.%s' % (config_version))


    @staticmethod
    def _parse_key(name):
        index = name.rfind(".")
        return name[:index], name[index+1:]


    def get(self, key, default):
        '''
        get value for key else return default
        '''
        value = self[key]
        if value is None:
            return default
        return value
        

    def __getitem__(self, key):
        section, option = _prefs._parse_key(key)
        # this doesn't allow None values for preferences
        if not self.config.has_section(section) or \
           not self.config.has_option(section, option):
            return None
        else:
            i = self.config.get(section, option)
            eval_chars = '{[(' 
            if i[0] in eval_chars: # then the value is a dict, list or tuple
                return eval(i)
            elif i == 'True' or i == 'False':
                return eval(i)
            return i
            #return self.config.get(section, option)

        
    def __setitem__(self, key, value):
        section, option = _prefs._parse_key(key)
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, str(value))

        
    def __contains__(self, key):
        section, option = _prefs._parse_key(key)
        if self.config.has_section(section) and \
           self.config.has_option(section, option):
            return True
        return False

    
    def save(self):
        f = open(self._filename, "w+")
        self.config.write(f)
        f.close()
                

#    def __del__(self, item):
#        """
#        """
#        section, option = _prefs._parse_key(item)
#        #if has section: remove option
#        # if n_option in section == -
#        #     remove section
#        
#        pass

            
prefs = _prefs()


