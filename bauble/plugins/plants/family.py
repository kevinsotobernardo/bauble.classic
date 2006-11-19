#
# Family table definition
#

import os, traceback
import gtk
from sqlalchemy import *
from sqlalchemy.orm.session import object_session
from sqlalchemy.exceptions import SQLError
import bauble
from bauble.editor import *
from datetime import datetime
import bauble.utils as utils
import bauble.utils.sql as sql_utils
from bauble.utils.log import debug
from bauble.types import Enum


def edit_callback(row):
    value = row[0]    
    e = FamilyEditor(model=value)
    return e.start() != None


def add_genera_callback(row):
    value = row[0]
    e = GenusEditor(Genus(family=value))
    return e.start() != None


def remove_callback(row):
    value = row[0]    
    s = '%s: %s' % (value.__class__.__name__, str(value))
    msg = "Are you sure you want to remove %s?" % utils.xml_safe(s)
    if not utils.yes_no_dialog(msg):
        return    
    try:
        session = create_session()
        obj = session.load(value.__class__, value.id)
        session.delete(obj)
        session.flush()
    except Exception, e:
        msg = 'Could not delete.\n\n%s' % utils.xml_safe(e)
        utils.message_details_dialog(msg, traceback.format_exc(), 
                                     type=gtk.MESSAGE_ERROR)
    return True


family_context_menu = [('Edit', edit_callback),
                       ('--', None),
                       ('Add genera', add_genera_callback),
                       ('--', None),
                       ('Remove', remove_callback)]

        
def family_markup_func(family):
    '''
    '''
    return family


#
# Family
#
family_table = Table('family',
                     Column('id', Integer, primary_key=True),
                     Column('family', String(45), nullable=False, index=True),
                     Column('qualifier', Enum(values=['s. lat.', 's. str.', None],
                                              empty_to_none=True)),
                     Column('notes', Unicode),
                     Column('_created', DateTime, default=func.current_timestamp()),
                     Column('_last_updated', DateTime, default=func.current_timestamp(), 
                            onupdate=func.current_timestamp()),
                     UniqueConstraint('family', 'qualifier', name='family_index'))

family_synonym_table = Table('family_synonym',
                             Column('id', Integer, primary_key=True),
                             Column('family_id', Integer, 
                                    ForeignKey('family.id'), 
                                    nullable=False),
                             Column('synonym_id', Integer, 
                                    ForeignKey('family.id'), 
                                    nullable=False),
                             Column('_created', DateTime, default=func.current_timestamp()),
                             Column('_last_updated', DateTime, default=func.current_timestamp(), 
                                    onupdate=func.current_timestamp()),
                             UniqueConstraint('family_id', 'synonym_id', name='family_synonym_index'))

class Family(bauble.BaubleMapper):
    
    def __str__(self): 
        # TODO: need ability to include the qualifier as part of the name, 
        # maybe as a keyworkd argument flag
        return Family.str(self)

    @staticmethod
    def str(family):
        if family.family is None:
            return repr(family)
        else:            
            return ' '.join([s for s in [family.family, family.qualifier] if s is not None])
    
    
class FamilySynonym(bauble.BaubleMapper):
    
    # - deleting either of the families that this synonym refers to 
    # makes this synonym irrelevant
    # - here default=None b/c this can only be edited as a sub editor of,
    # Family, thoughwe have to be careful this doesn't create a dangling record
    # with no parent
    def __init__(self, family=None, synonym=None):
        self.family = family
        self.synonym = synonym
        
    def __str__(self):
        return Family.str(self.synonym)
        
from bauble.plugins.plants.genus import Genus, genus_table, GenusEditor
#from bauble.plugins.plants.genus import Species, species_table
from bauble.plugins.garden.accession import Accession, accession_table
from bauble.plugins.garden.plant import Plant, plant_table

mapper(Family, family_table,
       properties = {'synonyms': relation(FamilySynonym, 
                                          primaryjoin=family_synonym_table.c.family_id==family_table.c.id,
                                          cascade='all, delete-orphan',
                                          backref='family'),
                     'genera': relation(Genus, backref='family')})
mapper(FamilySynonym, family_synonym_table,
       properties = {'synonym': relation(Family, uselist=False,
                                         primaryjoin=family_synonym_table.c.synonym_id==family_table.c.id),
                     'family': relation(Family, uselist=False, 
                                        primaryjoin=family_synonym_table.c.family_id==family_table.c.id)
                     })
    
    
class FamilyEditorView(GenericEditorView):
    
    syn_expanded_pref = 'editor.family.synonyms.expanded'

    def __init__(self, parent=None):
        GenericEditorView.__init__(self, os.path.join(paths.lib_dir(), 
                                                      'plugins', 'plants', 
                                                      'editors.glade'),
                                   parent=parent)
        self.dialog = self.widgets.family_dialog
        self.dialog.set_transient_for(parent)
        self.attach_completion('fam_syn_entry')#, self.syn_cell_data_func)
        self.connect_dialog_close(self.widgets.family_dialog)
        self.restore_state()

        
    def save_state(self):
        prefs[self.syn_expanded_pref] = self.widgets.fam_syn_expander.get_expanded()    

        
    def restore_state(self):
        expanded = prefs.get(self.syn_expanded_pref, True)
        self.widgets.fam_syn_expander.set_expanded(expanded)        


    def _get_window(self):
        '''
        '''
        return self.widgets.family_dialog    
    window = property(_get_window)
        
            
    def set_accept_buttons_sensitive(self, sensitive):
        self.widgets.fam_ok_button.set_sensitive(sensitive)
        self.widgets.fam_ok_and_add_button.set_sensitive(sensitive)
        self.widgets.fam_next_button.set_sensitive(sensitive)
        
        
    def start(self):
        return self.dialog.run()    
        

class FamilyEditorPresenter(GenericEditorPresenter):
    
    widget_to_field_map = {'fam_family_entry': 'family',
                           'fam_qualifier_combo': 'qualifier',
                           'fam_notes_textview': 'notes'}
    
    def __init__(self, model, view):
        '''
        @param model: should be an instance of class Accession
        @param view: should be an instance of AccessionEditorView
        '''
        GenericEditorPresenter.__init__(self, ModelDecorator(model), view)
        self.session = object_session(model)

        # initialize widgets
        self.init_enum_combo('fam_qualifier_combo', 'qualifier')
        self.synonyms_presenter = SynonymsPresenter(self.model, self.view, self.session)        
        self.refresh_view() # put model values in view            
        
        # connect signals
        self.assign_simple_handler('fam_family_entry', 'family')
        self.assign_simple_handler('fam_qualifier_combo', 'qualifier')
        self.assign_simple_handler('fam_notes_textview', 'notes')
        
        # for each widget register a signal handler to be notified when the
        # value in the widget changes, that way we can do things like sensitize
        # the ok button
        for field in self.widget_to_field_map.values():
            self.model.add_notifier(field, self.on_field_changed)
    
    
    def on_field_changed(self, model, field):
        self.view.set_accept_buttons_sensitive(True)
        

    def dirty(self):
        return self.model.dirty or self.synonyms_presenter.dirty()
    
    
    def refresh_view(self):
        for widget, field in self.widget_to_field_map.iteritems():
            value = self.model[field]
            self.view.set_widget_value(widget, value)
            
    
    def start(self):
        return self.view.start()
    
 
#
# TODO: you shouldn't be able to set a family as a synonym of itself
#
class SynonymsPresenter(GenericEditorPresenter):
    
    PROBLEM_INVALID_SYNONYM = 1
    
    # TODO: if you add a species and then immediately remove then you get an
    # error, something about the synonym not being in the session
        
    def __init__(self, family, view, session):
        '''
        @param model: Family instance
        @param view: see GenericEditorPresenter
        @param session: 
        '''
        GenericEditorPresenter.__init__(self, ModelDecorator(family), view)
        self.session = session
        self.init_treeview()
        
        # use completions_model as a dummy object for completions, we'll create
        # seperate SpeciesSynonym models on add
        completions_model = FamilySynonym()
        def fam_get_completions(text):           
            return self.session.query(Family).select(family_table.c.family.like('%s%%' % text))
        def set_in_model(self, field, value):
            # don't set anything in the model, just set self.selected
            sensitive = True
            if value is None:
                sensitive = False
            self.view.widgets.fam_syn_add_button.set_sensitive(sensitive)
            self._added = value

        self.assign_completions_handler('fam_syn_entry', 'synonym',
                                        fam_get_completions, 
                                        set_func=set_in_model,
                                        model=completions_model)
#        self.selected = None
        self._added = None
        self.view.widgets.fam_syn_add_button.connect('clicked', 
                                                    self.on_add_button_clicked)
        self.view.widgets.fam_syn_remove_button.connect('clicked', 
                                                    self.on_remove_button_clicked)
        self.__dirty = False
        
        
    def dirty(self):
        return self.model.dirty or self.__dirty
    
    
    def init_treeview(self):        
        '''
        initialize the gtk.TreeView
        '''
        self.treeview = self.view.widgets.fam_syn_treeview        
        def _syn_data_func(column, cell, model, iter, data=None):
            v = model[iter][0]
            cell.set_property('text', str(v))
            # just added so change the background color to indicate its new
            if v.id is None:
                cell.set_property('foreground', 'blue')
            else:
                cell.set_property('foreground', None)
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Synonym', cell)
        col.set_cell_data_func(cell, _syn_data_func)
        self.treeview.append_column(col)
        
        tree_model = gtk.ListStore(object)
        for syn in self.model.synonyms:
            tree_model.append([syn])
        self.treeview.set_model(tree_model)        
        self.treeview.connect('cursor-changed', self.on_tree_cursor_changed)
    
    
    def on_tree_cursor_changed(self, tree, data=None):
        '''
        '''
        path, column = tree.get_cursor()
        self.view.widgets.fam_syn_remove_button.set_sensitive(True)

    
    def refresh_view(self):
        '''
        doesn't do anything
        '''
        return
        
        
    def on_add_button_clicked(self, button, data=None):
        '''
        adds the synonym from the synonym entry to the list of synonyms for 
            this species
        '''        
        syn = FamilySynonym()
        syn.synonym = self._added        
        #self.session.save(syn)
        self.model.synonyms.append(syn)
        tree_model = self.treeview.get_model()
        tree_model.append([syn])
        self._added = None
        entry = self.view.widgets.fam_syn_entry
        # sid generated from GenericEditorPresenter.assign_completion_handler
        entry.handler_block(self._insert_fam_syn_entry_sid) 
        entry.set_text('')
        entry.set_position(-1)        
        entry.handler_unblock(self._insert_fam_syn_entry_sid)
        self.view.widgets.fam_syn_add_button.set_sensitive(False)
        self.view.widgets.fam_syn_add_button.set_sensitive(False)
        #self.view.set_accept_buttons_sensitive(True)
        self.__dirty = True
        

    def on_remove_button_clicked(self, button, data=None):
        '''
        removes the currently selected synonym from the list of synonyms for
        this species
        '''
        # TODO: maybe we should only ask 'are you sure' if the selected value
        # is an instance, this means it will be deleted from the database        
        tree = self.view.widgets.fam_syn_treeview
        path, col = tree.get_cursor()
        tree_model = tree.get_model()
        value = tree_model[tree_model.get_iter(path)][0]      
#        debug('%s: %s' % (value, type(value)))
        s = Family.str(value.synonym)
        msg = 'Are you sure you want to remove %s as a synonym to the ' \
              'current family?\n\n<i>Note: This will not remove the family '\
              '%s from the database.</i>' % (s, s)
        if utils.yes_no_dialog(msg, parent=self.view.window):            
            tree_model.remove(tree_model.get_iter(path))
            self.model.synonyms.remove(value)
#            delete_or_expunge(value)            
            #self.view.set_accept_buttons_sensitive(True)
            self.__dirty = True
            
               
class FamilyEditor(GenericModelViewPresenterEditor):
    
    label = 'Family'
    mnemonic_label = '_Family'
    
    # these have to correspond to the response values in the view
    RESPONSE_OK_AND_ADD = 11
    RESPONSE_NEXT = 22
    ok_responses = (RESPONSE_OK_AND_ADD, RESPONSE_NEXT)    
        
        
    def __init__(self, model=None, parent=None):
        '''
        @param model: Family instance or None
        @param parent: the parent window or None
        '''        
        if model is None:
            model = Family()

        GenericModelViewPresenterEditor.__init__(self, model, parent)
        if parent is None: # should we even allow a change in parent
            parent = bauble.app.gui.window
        self.parent = parent
        self._committed = []
    
    
    def handle_response(self, response):
        '''
        @return: return a list if we want to tell start() to close the editor, 
        the list should either be empty or the list of committed values, return 
        None if we want to keep editing
        '''
        not_ok_msg = 'Are you sure you want to lose your changes?'        
        if response == gtk.RESPONSE_OK or response in self.ok_responses:
            try:
                if self.presenter.dirty():
                    self.commit_changes()
                    self._committed.append(self.model)
            except SQLError, e:                
                msg = 'Error committing changes.\n\n%s' % utils.xml_safe(e.orig)
                utils.message_details_dialog(msg, str(e), gtk.MESSAGE_ERROR)
                return False
            except Exception, e:
                msg = 'Unknown error when committing changes. See the details '\
                      'for more information.\n\n%s' % utils.xml_safe(e)
                utils.message_details_dialog(msg, traceback.format_exc(), 
                                             gtk.MESSAGE_ERROR)
                return False
        elif self.presenter.dirty() and utils.yes_no_dialog(not_ok_msg) or not self.presenter.dirty():
            return True
        else:
            return False
                
        # respond to responses
        more_committed = None
        if response == self.RESPONSE_NEXT:
            e = FamilyEditor(parent=self.parent)
            more_committed = e.start()
        elif response == self.RESPONSE_OK_AND_ADD:
            e = GenusEditor(Genus(family=self.model), self.parent)
            more_committed = e.start()
                      
        if more_committed is not None:
            if isinstance(more_committed, list):
                self._committed.extend(more_committed)
            else:
                self._committed.append(more_committed)                
        
        return True            
        
    
    def start(self):
        self.view = FamilyEditorView(parent=self.parent)
        self.presenter = FamilyEditorPresenter(self.model, self.view)
        
        # add quick response keys
        dialog = self.view.dialog
        self.attach_response(dialog, gtk.RESPONSE_OK, 'Return', gtk.gdk.CONTROL_MASK)
        self.attach_response(dialog, self.RESPONSE_OK_AND_ADD, 'k', gtk.gdk.CONTROL_MASK)
        self.attach_response(dialog, self.RESPONSE_NEXT, 'n', gtk.gdk.CONTROL_MASK)        
        
        exc_msg = "Could not commit changes.\n"
        committed = None
        while True:
            response = self.presenter.start()
            self.view.save_state() # should view or presenter save state
            if self.handle_response(response):
                break            
        self.session.close() # cleanup session
        return self._committed


#
# Family infobox
#

# TODO: need to hook up the notes box

try:
    from bauble.plugins.searchview.infobox import InfoBox, InfoExpander    
except ImportError, e:    
    pass
else:    
    import bauble.paths as paths
    from bauble.plugins.plants.genus import Genus
    from bauble.plugins.plants.species_model import Species, species_table
    from bauble.plugins.garden.accession import Accession
    from bauble.plugins.garden.plant import Plant
    
    class GeneralFamilyExpander(InfoExpander):
        '''
        generic information about an family like number of genus, species,
        accessions and plants
        '''
    
        def __init__(self, widgets):
            '''
            the constructor
            '''
            InfoExpander.__init__(self, "General", widgets)
            general_box = self.widgets.fam_general_box
            self.widgets.remove_parent(general_box)                
            self.vbox.pack_start(general_box)
            
            
        def update(self, row):
            '''
            update the expander
            
            @param row: the row to get the values from
            '''
                        
            self.set_widget_value('fam_name_data', str(row))
            
            # get the number of genera
            genus_ids = select([genus_table.c.id], genus_table.c.family_id==row.id)
            ngen = sql_utils.count_select(genus_ids)
            self.set_widget_value('fam_ngen_data', ngen)
            
            # get the number of species            
            species_ids = select([species_table.c.id], species_table.c.genus_id.in_(genus_ids))
            nsp_str = str(sql_utils.count_select(species_ids))    
            if nsp_str != '0': 
                ngen_with_species = sql_utils.count_distinct_whereclause(species_table.c.genus_id, species_table.c.genus_id.in_(genus_ids))
                nsp_str = '%s in %s genera' % (nsp_str, ngen_with_species)            
            self.set_widget_value('fam_nsp_data', nsp_str)
            
            # get the number of accessions
            acc_ids = select([accession_table.c.id], accession_table.c.species_id.in_(species_ids))
            nacc_str = str(sql_utils.count_select(acc_ids))
            if nacc_str != '0':
                nsp_with_accessions = sql_utils.count_distinct_whereclause(accession_table.c.species_id, accession_table.c.species_id.in_(species_ids))
                nacc_str = '%s in %s species' % (nacc_str, nsp_with_accessions)            
            self.set_widget_value('fam_nacc_data', nacc_str)
            
            # get the number of plants
            nplants_str = str(sql_utils.count(plant_table, plant_table.c.accession_id.in_(acc_ids)))
            if nplants_str != '0':
                nacc_with_plants = sql_utils.count_distinct_whereclause(plant_table.c.accession_id, plant_table.c.accession_id.in_(acc_ids))
                nplants_str = '%s in %s accessions' % (nplants_str, nacc_with_plants)
            self.set_widget_value('fam_nplants_data', nplants_str)

                
                
    class FamilyInfoBox(InfoBox):
        '''
        '''
        
        def __init__(self):
            '''
            '''
            InfoBox.__init__(self)
            glade_file = os.path.join(paths.lib_dir(), 'plugins', 'plants', 
                                      'infoboxes.glade')            
            self.widgets = utils.GladeWidgets(gtk.glade.XML(glade_file))
            self.general = GeneralFamilyExpander(self.widgets)
            self.add_expander(self.general)
        
        def update(self, row):
            '''
            '''
            self.general.update(row)