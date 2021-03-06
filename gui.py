import threading
import wx
import wx.grid
import os
import re
import logging
from modules.helpers.parser import FlagConfigParser
from cefpython3.wx import chromectrl
# ToDO: Support customization of borders/spacings
# ToDO: Exit by cancel button

TRANSLATIONS = {}
IDS = {}
log = logging.getLogger('chat_gui')
MODULE_KEY = '.'
INFORMATION_TAG = 'gui_information'
SECTION_GUI_TAG = '__gui'
SKIP_TAGS = [INFORMATION_TAG]
SKIP_TXT_CONTROLS = ['list_input', 'list_input2']
SKIP_BUTTONS = ['list_add', 'list_remove']


def get_id_from_name(name, error=False):
    for item, item_id in IDS.items():
        if item_id == name:
            return item
    if error:
        raise ReferenceError
    return None


def id_renew(name, update=False):
    module_id = get_id_from_name(name)
    if module_id:
        del IDS[module_id]
    new_id = wx.Window.NewControlId(1)
    if update:
        IDS[new_id] = name
    return new_id


def get_list_of_ids_from_module_name(name, id_group=1, tuple=False):
    split_key = MODULE_KEY

    id_array = []
    for item_key, item in IDS.items():
        item_name = split_key.join(item.split(split_key)[:id_group])
        if item_name == name:
            if tuple:
                id_array.append((item_key, item))
            else:
                id_array.append(item_key)
    return id_array


def fix_sizes(size1, size2):
    if size1[0] > size2[0]:
        label_x_size = size1[0]
    else:
        label_x_size = size2[0]

    if size1[1] > size2[1]:
        label_y_size = size1[1]
    else:
        label_y_size = size2[1]
    return [label_x_size, label_y_size]


def load_translations(settings, language):
    language = language.lower()
    conf_file = 'translations.cfg'
    config = FlagConfigParser(allow_no_value=True)
    config.read(os.path.join(settings['folder'], conf_file))

    if not config.has_section(language):
        log.warning("Warning, have not found language: {0}".format(language))
        language = 'english'

    for param, value in config.items(language):
        TRANSLATIONS[param] = value


def find_translation(item, length=0, wildcard=1):
    translation = TRANSLATIONS.get(item, item)
    if item == translation:
        if wildcard < length:
            translation = find_translation(MODULE_KEY.join(['*'] + item.split(MODULE_KEY)[-wildcard:]),
                                           length=length, wildcard=wildcard+1)
        else:
            return translation
    return translation


def translate(item):
    item_no_flags = item.split('/')[0]
    old_item = item_no_flags

    translation = find_translation(item_no_flags, length=len(item_no_flags.split(MODULE_KEY)))

    if re.match('\*', translation):
        return old_item
    return translation.decode('utf-8')


def check_duplicate(item, window):
    items = window.GetItems()
    if item in items:
        return True
    return False


def create_categories(loaded_modules):
    cat_dict = {}
    for module_name, module_config in loaded_modules.items():
        parser = module_config['parser']  # type: FlagConfigParser
        if parser.has_section(INFORMATION_TAG) and parser.has_option(INFORMATION_TAG, 'category'):
            tag = parser.get(INFORMATION_TAG, 'category')
            item_dict = {module_name: module_config}
            for key, value in parser.items(INFORMATION_TAG):
                if key == 'hidden':
                    item_dict[module_name][key] = [h_item.strip() for h_item in value.split(',')]
            if tag in cat_dict:
                cat_dict[tag].append(item_dict)
            else:
                cat_dict[tag] = [item_dict]
    return cat_dict


class MainMenuToolBar(wx.ToolBar):
    def __init__(self, *args, **kwargs):
        self.main_class = kwargs['main_class']
        kwargs.pop('main_class')

        kwargs["style"] = wx.TB_NOICONS | wx.TB_TEXT

        wx.ToolBar.__init__(self, *args, **kwargs)
        self.SetToolBitmapSize((0, 0))

        self.create_tool('menu.settings', self.main_class.on_settings)
        self.create_tool('menu.reload', self.main_class.on_about)

        self.Realize()

    def create_tool(self, name, binding=None, style=wx.ITEM_NORMAL, s_help="", l_help=""):
        l_id = id_renew(name)
        IDS[l_id] = name
        label_text = translate(IDS[l_id])
        button = self.AddLabelTool(l_id, label_text, wx.NullBitmap, wx.NullBitmap,
                                   style, s_help, l_help)
        if binding:
            self.main_class.Bind(wx.EVT_TOOL, binding, id=l_id)
        return button


class SettingsWindow(wx.Frame):
    main_grid = None
    notebook = None
    page_list = []
    selected_cell = None

    def __init__(self, *args, **kwargs):
        self.spacer_size = (0, 10)
        self.main_class = kwargs.pop('main_class')  # type: ChatGui

        wx.Frame.__init__(self, *args, **kwargs)

        # Setting up the window
        self.SetBackgroundColour('cream')
        self.show_hidden = self.main_class.gui_settings.get('show_hidden')

        # Setting up events
        self.Bind(wx.EVT_CLOSE, self.on_close_save)

        styles = wx.DEFAULT_FRAME_STYLE
        if wx.STAY_ON_TOP & self.main_class.GetWindowStyle() == wx.STAY_ON_TOP:
            styles = styles | wx.STAY_ON_TOP
        self.SetWindowStyle(styles)

        self.create_layout()

    def on_exit(self, event):
        self.Destroy()

    def on_close(self, event):
        dialog = wx.MessageDialog(self, message="Are you sure you want to quit?",
                                  caption="Caption",
                                  style=wx.YES_NO,
                                  pos=wx.DefaultPosition)
        response = dialog.ShowModal()

        if response == wx.ID_YES:
            self.on_exit(event)
        else:
            event.StopPropagation()

    def on_close_save(self, event):
        dialog = wx.MessageDialog(self, message="Are you sure you want to quit?\n"
                                                "Warning, your settings will not be saved.",
                                  caption="Caption",
                                  style=wx.YES_NO,
                                  pos=wx.DefaultPosition)
        response = dialog.ShowModal()

        if response == wx.ID_YES:
            self.on_exit(event)
        else:
            event.StopPropagation()

    def create_layout(self):
        self.main_grid = wx.BoxSizer(wx.VERTICAL)
        style = wx.NB_TOP
        self.notebook = wx.Notebook(self, id=wx.ID_ANY, style=style)
        self.main_grid.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(self.main_grid)
        self.Show(True)

    def remove_pages(self, key):
        for item in range(self.notebook.GetPageCount()):
            text = self.notebook.GetPageText(0)
            if not key == text and key not in self.page_list:
                self.notebook.DeletePage(0)

    def fill_notebook_with_modules(self, category_list, setting_category):
        page_list = []
        for category_dict in category_list:
            category_item, category_config = category_dict.iteritems().next()
            translated_item = translate(category_item)
            if translated_item not in self.page_list:
                panel = wx.Panel(self.notebook)
                self.fill_page_with_content(panel, setting_category, category_item, category_config)
                self.notebook.AddPage(panel, translated_item)
                page_list.append(translated_item)
            else:
                page_list.append(translated_item)
        self.page_list = page_list

    def fill_page_with_content(self, panel, setting_category, category_item, category_config):
        def create_button(button_key, function):
            button_id = id_renew(button_key, update=True)
            c_button = wx.Button(panel, id=button_id, label=translate(button_key))
            self.Bind(wx.EVT_BUTTON, function, id=button_id)
            return c_button

        # Creating sizer for page
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Window for settings
        page_sc_window = wx.ScrolledWindow(panel, id=id_renew(category_item), style=wx.VSCROLL)
        page_sc_window.SetScrollbars(5, 5, 10, 10)

        config = self.prepare_config_for_window(category_config)

        self.fill_sc_with_config(page_sc_window, config, category_item)

        sizer.Add(page_sc_window, 1, wx.EXPAND)
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for button_name in ['apply_button', 'cancel_button']:
            button_sizer.Add(create_button(MODULE_KEY.join([setting_category, category_item, button_name]),
                                           self.button_clicked), 0, wx.ALIGN_RIGHT)
        sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT)
        panel.SetSizer(sizer)
        panel.Layout()
        pass

    def fill_sc_with_config(self, page_sc_window, config, category_item):
        border_all = 5
        sizer = wx.BoxSizer(wx.VERTICAL)
        for section in config['sections']:
            section_key, section_tuple = section
            if section_key in SKIP_TAGS:
                continue

            static_key = MODULE_KEY.join([category_item, section_key])
            static_box = wx.StaticBox(page_sc_window, label=translate(static_key))
            static_sizer = wx.StaticBoxSizer(static_box, wx.VERTICAL)

            log.debug("Working on {0}".format(static_key))

            view = 'normal'
            if section_key in config['gui']:  # type: dict
                log.debug('{0} has gui settings'.format(static_key))
                view = config['gui'][section_key].get('view', 'normal')

            static_sizer.Add(self.create_items(static_box, static_key,
                                               view, section_tuple, config['gui'].get(section_key, {})),
                             0, wx.EXPAND | wx.ALL, border_all)

            sizer.Add(static_sizer, 0, wx.EXPAND)
        page_sc_window.SetSizer(sizer)

    @staticmethod
    def prepare_config_for_window(category_config):
        parser = FlagConfigParser(allow_no_value=True)  # type: FlagConfigParser
        parser.readfp(open(category_config['file']))
        config_dict = {'gui': {}, 'sections': []}
        for section in parser.sections():
            if SECTION_GUI_TAG in section:
                gui_dict = {}
                section_items = None
                for item, value in parser.items(section):
                    if item == 'for':
                        section_items = [value_item.strip() for value_item in value.split(',')]
                    elif item == 'hidden':
                        gui_dict[item] = [value_item.strip() for value_item in value.split(',')]
                    else:
                        gui_dict[item] = value

                if section_items:
                    for section_item in section_items:
                        config_dict['gui'][section_item] = gui_dict
            else:
                tag_values = []
                for item, value in parser.items(section):
                    tag_values.append((item, value))
                config_dict['sections'].append((section, tag_values))
        return config_dict

    def create_items(self, parent, key, view, section, section_gui):
        sizer = wx.BoxSizer(wx.VERTICAL)
        addable_sizer = None
        if 'list' in view:
            is_dual = True if 'dual' in view else False
            style = wx.ALIGN_CENTER_VERTICAL
            item_sizer = wx.BoxSizer(wx.VERTICAL)
            if section_gui.get('addable', False):
                addable_sizer = wx.BoxSizer(wx.HORIZONTAL)
                item_input_key = MODULE_KEY.join([key, 'list_input'])
                addable_sizer.Add(wx.TextCtrl(parent, id=id_renew(item_input_key, update=True)), 0, style)
                if is_dual:
                    item_input2_key = MODULE_KEY.join([key, 'list_input2'])
                    addable_sizer.Add(wx.TextCtrl(parent, id=id_renew(item_input2_key, update=True)), 0, style)

                item_apply_key = MODULE_KEY.join([key, 'list_add'])
                item_apply_id = id_renew(item_apply_key, update=True)
                addable_sizer.Add(wx.Button(parent, id=item_apply_id, label=translate(item_apply_key)), 0, style)
                self.Bind(wx.EVT_BUTTON, self.button_clicked, id=item_apply_id)

                item_remove_key = MODULE_KEY.join([key, 'list_remove'])
                item_remove_id = id_renew(item_remove_key, update=True)
                addable_sizer.Add(wx.Button(parent, id=item_remove_id, label=translate(item_remove_key)), 0, style)
                self.Bind(wx.EVT_BUTTON, self.button_clicked, id=item_remove_id)

                item_sizer.Add(addable_sizer, 0, wx.EXPAND)
            list_box = wx.grid.Grid(parent, id=id_renew(MODULE_KEY.join([key, 'list_box']), update=True))
            list_box.CreateGrid(0, 2 if is_dual else 1)
            list_box.DisableDragColSize()
            list_box.DisableDragRowSize()
            list_box.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.select_cell)

            for index, items in enumerate(section):
                item, value = items
                list_box.AppendRows(1)
                if is_dual:
                    list_box.SetCellValue(index, 0, item.decode('utf-8'))
                    list_box.SetCellValue(index, 1, value.decode('utf-8'))
                else:
                    list_box.SetCellValue(index, 0, item.decode('utf-8'))
            list_box.SetColLabelSize(1)
            list_box.SetRowLabelSize(1)
            if addable_sizer:
                col_size = addable_sizer.GetMinSize()[0] - 2
                if is_dual:
                    first_col_size = list_box.GetColSize(0)
                    second_col_size = col_size - first_col_size if first_col_size < col_size else -1
                    list_box.SetColSize(1, second_col_size)
                else:
                    list_box.SetDefaultColSize(col_size, resizeExistingCols=True)
            else:
                list_box.AutoSize()

            # Adding size of scrollbars
            size = list_box.GetEffectiveMinSize()
            size[0] += 18
            size[1] += 18
            list_box.SetMinSize(size)
            item_sizer.Add(list_box, 1, wx.EXPAND)

            sizer.Add(item_sizer)
        else:
            items_to_add = []
            if not section:
                return sizer
            last_item = section[-1][0]
            for item, value in section:
                if not self.show_hidden and 'hidden' in section_gui and item in section_gui.get('hidden'):
                    continue
                item_name = MODULE_KEY.join([key, item])
                # Checking type of an item
                style = wx.ALIGN_CENTER_VERTICAL
                if not value:  # Button
                    button_id = id_renew(item_name, update=True)
                    item_button = wx.Button(parent, id=button_id, label=translate(item_name))
                    items_to_add.append((item_button, 0, wx.ALIGN_LEFT))
                    self.main_class.Bind(wx.EVT_BUTTON, self.button_clicked, id=button_id)
                elif value.lower() in ['true', 'false']:  # Checkbox
                    item_box = wx.CheckBox(parent, id=id_renew(item_name, update=True),
                                           label=translate(item_name), style=style)
                    item_box.SetValue(True if value.lower() == 'true' else False)
                    items_to_add.append((item_box, 0, wx.ALIGN_LEFT))
                else:  # TextCtrl
                    item_sizer = wx.BoxSizer(wx.HORIZONTAL)
                    item_box = wx.TextCtrl(parent, id=id_renew(item_name, update=True),
                                           value=value.decode('utf-8'))
                    item_text = wx.StaticText(parent, label=translate(item_name),
                                              style=wx.ALIGN_RIGHT)
                    item_spacer = (10, 0)
                    item_sizer.AddMany([(item_text, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL),
                                        (item_spacer, 0, 0),
                                        (item_box, 0)])
                    items_to_add.append(item_sizer)
                if not item == last_item:
                    items_to_add.append((self.spacer_size, 0, 0))
            sizer.AddMany(items_to_add)
        return sizer

    def button_clicked(self, event):
        log.debug("[Settings] Button clicked: {0}".format(IDS[event.GetId()]))
        button_id = event.GetId()
        keys = IDS[button_id].split(MODULE_KEY)
        if keys[-1] in ['list_add', 'list_remove']:
            self.list_operation(MODULE_KEY.join(keys[:-1]), action=keys[-1])
        elif keys[-1] == 'apply_button':
            self.save_settings(MODULE_KEY.join(keys[1:-1]), MODULE_KEY.join(keys[:-1]))
        elif keys[-1] == 'cancel_button':
            self.on_close(event)
        event.Skip()

    def save_settings(self, module, key):
        module_config = self.main_class.loaded_modules.get(module, {})
        if module_config:
            parser = module_config['parser']
            items = get_list_of_ids_from_module_name(module, tuple=True)
            for item, name in items:
                module_name, section, item_name = name.split(MODULE_KEY)
                wx_window = wx.FindWindowById(item)
                if isinstance(wx_window, wx.CheckBox):
                    if name == MODULE_KEY.join(['config', 'gui', 'show_hidden']):
                        self.show_hidden = wx_window.IsChecked()
                    parser.set(section, item_name, wx_window.IsChecked())
                elif isinstance(wx_window, wx.TextCtrl):
                    if item_name not in SKIP_TXT_CONTROLS:
                        parser.set(section, item_name, wx_window.GetValue().encode('utf-8'))
                elif isinstance(wx_window, wx.grid.Grid):
                    col_count = wx_window.GetNumberCols()
                    row_count = wx_window.GetNumberRows()
                    parser_options = parser.options(section)
                    grid_elements = [[wx_window.GetCellValue(row, col).encode('utf-8')
                                      for col in range(col_count)]
                                     for row in range(row_count)]
                    if not grid_elements:
                        for option in parser_options:
                            parser.remove_option(section, option)
                    else:
                        for option in parser_options:
                            for elements in grid_elements:
                                if option not in elements:
                                    parser.remove_option(section, option)
                        for elements in grid_elements:
                            parser.set(section, *elements)
                elif isinstance(wx_window, wx.Button):
                    if item_name not in SKIP_BUTTONS:
                        parser.set(section, item_name)

            with open(module_config['file'], 'w') as config_file:
                parser.write(config_file)

    def select_cell(self, event):
        self.selected_cell = (event.GetRow(), event.GetCol())
        event.Skip()

    def list_operation(self, key, action):
        if action == 'list_add':
            list_input_value = wx.FindWindowById(get_id_from_name(MODULE_KEY.join([key, 'list_input']))).GetValue()

            try:
                list_input2 = wx.FindWindowById(get_id_from_name(MODULE_KEY.join([key, 'list_input2']), error=True))
                list_input2_value = list_input2.GetValue() if list_input2 else None
            except ReferenceError:
                list_input2_value = None

            list_box = wx.FindWindowById(get_id_from_name(MODULE_KEY.join([key, 'list_box'])))
            list_box.AppendRows(1)
            row_count = list_box.GetNumberRows() - 1
            list_box.SetCellValue(row_count, 0, list_input_value)
            if list_input2_value:
                list_box.SetCellValue(row_count, 1, list_input2_value)

        elif action == 'list_remove':
            list_box = wx.FindWindowById(get_id_from_name(MODULE_KEY.join([key, 'list_box'])))
            top = list_box.GetSelectionBlockTopLeft()
            bot = list_box.GetSelectionBlockBottomRight()
            if top and bot:
                top = top[0][0]
                bot = bot[0][0] + 1
                del_rows = range(top, bot) if top < bot else range(bot, top)
            else:
                del_rows = [self.selected_cell[0]]

            if list_box.GetNumberRows():
                ids_deleted = 0
                for select in del_rows:
                    list_box.DeleteRows(select - ids_deleted)
                    ids_deleted += 1


class ChatGui(wx.Frame):
    settings_window = None

    def __init__(self, parent, title, url, **kwargs):
        wx.Frame.__init__(self, parent, title=title, size=(450, 500))

        # Setting the settings
        self.main_config = kwargs.get('main_config')
        self.gui_settings = kwargs.get('gui_settings')
        self.loaded_modules = kwargs.get('loaded_modules')

        # Set window style
        styles = wx.DEFAULT_FRAME_STYLE
        if self.gui_settings.get('on_top', False):
            log.info("Application is on top")
            styles = styles | wx.STAY_ON_TOP
        self.SetFocus()
        self.SetWindowStyle(styles)

        # Creating categories for gui
        log.debug("Sorting modules to categories")
        self.sorted_categories = create_categories(self.loaded_modules)

        # Creating main gui window
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.toolbar = MainMenuToolBar(self, main_class=self)
        self.settings_menu = self.create_menu("settings", self.sorted_categories)
        self.browser_window = chromectrl.ChromeCtrl(self, useTimer=False, url=str(url), hasNavBar=False)

        vbox.Add(self.toolbar, 0, wx.EXPAND)
        vbox.Add(self.browser_window, 1, wx.EXPAND)

        # Set events
        self.Bind(wx.EVT_CLOSE, self.on_exit)

        # Show window after creation
        self.SetSizer(vbox)
        self.Show(True)

    def on_about(self, event):
        self.browser_window.Refresh()
        event.Skip()

    def on_exit(self, event):
        log.info("Exiting...")
        self.Destroy()
        event.Skip()

    def on_right_down(self, event):
        log.info("RClick")
        event.Skip()

    def on_settings(self, event):
        log.debug("Opening menu {0}".format(IDS[event.GetId()]))
        tool_index = self.toolbar.GetToolPos(get_id_from_name('menu.settings'))
        tool_size = self.toolbar.GetToolSize()
        bar_position = self.toolbar.GetScreenPosition() - self.GetScreenPosition()
        offset = tool_size[0] + (1 * tool_index)
        lower_left_corner = (bar_position[0] + (offset * tool_index),
                             bar_position[1] + tool_size[1])
        menu_position = (lower_left_corner[0] - bar_position[0],
                         lower_left_corner[1] - bar_position[1])

        self.PopupMenu(self.settings_menu, menu_position)
        event.Skip()

    def on_settings_button(self, event):
        log.debug("Got event from {0}".format(IDS[event.GetId()]))
        module_groups = IDS[event.GetId()].split(MODULE_KEY)
        settings_category = MODULE_KEY.join(module_groups[1:-1])
        settings_menu_id = id_renew(settings_category, update=True)
        if self.settings_window:
            self.settings_window.notebook.Show(False)
            self.settings_window.SetFocus()
            self.settings_window.SetTitle(translate(MODULE_KEY.join(module_groups[:-1])))
            self.settings_window.remove_pages(translate(module_groups[-1]))
        else:
            self.settings_window = SettingsWindow(self,
                                                  id=settings_menu_id,
                                                  title=translate(MODULE_KEY.join(module_groups[:-1])),
                                                  size=(500, 400),
                                                  main_class=self)

        self.settings_window.fill_notebook_with_modules(self.sorted_categories[settings_category], settings_category)
        self.settings_window.notebook.SetSelection(self.settings_window.page_list.index(translate(module_groups[-1])))
        self.settings_window.notebook.Show(True)
        event.Skip()

    def create_menu(self, name, modules, menu_named=False):
        settings_menu = wx.Menu(translate(name)) if menu_named else wx.Menu()
        # Creating menu items
        for category, category_items in modules.items():
            category_name = MODULE_KEY.join([name, category])
            category_sub_menu = wx.Menu()
            for category_dict in category_items:
                category_item_name, settings = category_dict.iteritems().next()
                sub_name = MODULE_KEY.join([category_name, category_item_name])
                category_menu_item = category_sub_menu.Append(id_renew(sub_name, update=True),
                                                              translate(category_item_name))
                self.Bind(wx.EVT_MENU, self.on_settings_button, id=category_menu_item.GetId())
            settings_menu.AppendSubMenu(category_sub_menu, translate(category_name))
        return settings_menu

    def button_clicked(self, event):
        log.debug("[ChatGui] Button clicked: {0}".format(IDS[event.GetId()]))
        button_id = event.GetId()
        keys = IDS[event.GetId()].split(MODULE_KEY)
        event.Skip()


class GuiThread(threading.Thread):
    title = 'LalkaChat'
    url = 'http://localhost'
    port = '8080'

    def __init__(self, **kwds):
        threading.Thread.__init__(self)
        self.daemon = True
        self.gui_settings = kwds.get('gui_settings', {})
        self.loaded_modules = kwds.get('loaded_modules', {})
        self.main_config = kwds.get('main_config', {})
        if 'webchat' in self.loaded_modules:
            self.port = self.loaded_modules['webchat']['port']

    def run(self):
        chromectrl.Initialize()
        url = ':'.join([self.url, self.port])
        load_translations(self.main_config, self.gui_settings.get('language', 'default'))
        app = wx.App(False)  # Create a new app, don't redirect stdout/stderr to a window.
        frame = ChatGui(None, "LalkaChat", url, main_config=self.main_config, gui_settings=self.gui_settings,
                        loaded_modules=self.loaded_modules)  # A Frame is a top-level window.
        app.MainLoop()
