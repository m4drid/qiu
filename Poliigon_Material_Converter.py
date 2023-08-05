# -*- coding: utf-8 -*-
# #### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import os
import sys
import json
import time
#pEFile = os.path.expanduser('~').replace('\\','/') + '/Poliigon/C4D_PMC_ErrorLog.txt'
#print (pEFile)
#sys.stderr = open(pEFile, 'w')

import copy
try :
    import ConfigParser
except :
    import configparser as ConfigParser

import c4d
import settings_dialog as PMCSettings
# Remember to set __res__ before using

# Version of this c4d Poliigon Material Converter
PMCversion = None
Pmaterial = '?'

# the plugin ID for Poliigon Material Converter & Internal version (will be registerd as a diffrent plugin)
PLUGIN_ID = 1040646
INTERNAL_PLUGIN_ID = 1041150

PLUGIN_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Set true to run the internal version of the converter
internal = False

__res__ = None

# Set true if you want to run the code from within the C4D Script Manager
RUN_FROM_EDITOR = False

# Get current version of C4D
C4D_version = c4d.GetC4DVersion()

# Windows
WarningWindow = None
ErrorDialog = None
dialog = None

# Save the default c4d exception hook
DefaultExceptionHook = sys.excepthook


def p_Str(pStr) :
    if sys.version.startswith('3.') :
        return str(pStr)
    else :
        try : return str(pStr.encode('utf-8'))
        except : return str(pStr)


# Material Preview
class MaterialPreview(c4d.gui.GeUserArea):
    def __init__(self, bmp):
      super(MaterialPreview, self).__init__()
      self._bmp = bmp

    def DrawMsg(self, x1, y1, x2, y2, msg):
      #self.DrawSetPen(c4d.Vector(0))
      #self.DrawRectangle(0, 0, 42, 42)
      if not self._bmp: return

      coords = self.Local2Global()
      self.DrawBitmap(self._bmp, 0, 0, 42, 42, 0, 0, 42, 42, c4d.BMP_NORMAL | c4d.BMP_ALLOWALPHA)

    def GetMinSize(self):
      return 42, 42

    def setBitmap(self, bmp):
      self._bmp = bmp


class TextureObject(object):
    """
    Class which represent a texture, aka an Item in our list
    """
    texturePath = "TexPath"
    MaterialInfo = ""
    _selected = False
    IsActive = False
    bLoaded = False
    workflow = "DIALECTRIC"
    MaterialName = ""

    def __init__(self, texturePath):
        self.texturePath = texturePath

    @property
    def IsSelected(self):
        return self._selected

    def Select(self):
        dialog.UpdateUI("MaterialsToLoad")
        self._selected = True

    def Deselect(self):
        dialog.UpdateUI("MaterialsToLoad")
        self._selected = False

    def __repr__(self):
        return self.MaterialName

    def __str__(self):
        return self.texturePath


class ListView(c4d.gui.TreeViewFunctions):

    def __init__(self):

        self.listOfTexture = list()

        # Load icons
        IconLoadedPath = os.path.join(PLUGIN_PATH, "res", "images", "poliigon_loaded.png")
        IconWarningPath = os.path.join(PLUGIN_PATH, "res", "images", "poliigon_warning.png")

        self.IconLoaded = c4d.bitmaps.BaseBitmap()
        self.IconLoaded.InitWith(IconLoadedPath)
        self.IconWarning = c4d.bitmaps.BaseBitmap()
        self.IconWarning.InitWith(IconWarningPath)

    def GetAllChecked(self):
        ListOfCheckedMaterials = []
        for obj in self.listOfTexture:
            if obj.IsSelected:
                ListOfCheckedMaterials.append(obj)
        return ListOfCheckedMaterials

    def IsResizeColAllowed(self, root, userdata, lColID):
        return True

    def IsTristate(self, root, userdata):
        return False

    def GetColumnWidth(self, root, userdata, obj, col, area):
        return 80  # All have the same initial width

    def IsMoveColAllowed(self, root, userdata, lColID):
        return True

    def GetFirst(self, root, userdata):
        """
       Return the first element in the hierarchy, or None if there is no element.
       """
        rValue = None if not self.listOfTexture else self.listOfTexture[0]
        return rValue

    def GetDown(self, root, userdata, obj):
        """
       Return a child of a node, since we only want a list, we return None everytime
       """
        return None

    def GetNext(self, root, userdata, obj):
        """
       Returns the next Object to display after arg:'obj'
       """
        rValue = None
        currentObjIndex = self.listOfTexture.index(obj)
        nextIndex = currentObjIndex + 1
        if nextIndex < len(self.listOfTexture):
            rValue = self.listOfTexture[nextIndex]

        return rValue

    def GetPred(self, root, userdata, obj):
        """
       Returns the previous Object to display before arg:'obj'
       """
        rValue = None
        currentObjIndex = self.listOfTexture.index(obj)
        predIndex = currentObjIndex - 1
        if 0 <= predIndex < len(self.listOfTexture):
            rValue = self.listOfTexture[predIndex]

        return rValue

    def GetId(self, root, userdata, obj):
        """
       Return a unique ID for the element in the TreeView.
       """
        return hash(obj)

    def Select(self, root, userdata, obj, mode):
        if mode == c4d.SELECTION_NEW:
            for tex in self.listOfTexture:
                tex.IsActive = False
            obj.IsActive = True
            dialog.UpdateMaterialSelection(obj)
        elif mode == c4d.SELECTION_ADD:
            obj.Select()
        elif mode == c4d.SELECTION_SUB:
            obj.Deselect()

    def IsSelected(self, root, userdata, obj):
        """
       Returns: True if *obj* is selected, False if not.
       """
        return obj.IsSelected

    def SetCheck(self, root, userdata, obj, column, checked, msg):
        if checked:
            obj.Select()
            #dialog.AddToMaterialList(obj)
        else:
            obj.Deselect()
            #dialog.RemoveFromMaterialList(obj)

    def IsChecked(self, root, userdata, obj, column):
        """
       Returns: (int): Status of the checkbox in the specified *column* for *obj*.
       """
        if obj.IsSelected:
            return c4d.LV_CHECKBOX_CHECKED | c4d.LV_CHECKBOX_ENABLED
        else:
            return c4d.LV_CHECKBOX_ENABLED

    def GetName(self, root, userdata, obj):
        """
       Returns the name to display for arg:'obj', only called for column of type LV_TREE
       """
        return obj.MaterialName # Or obj.texturePath

    def DrawCell(self, root, userdata, obj, col, drawinfo, bgColor):
        """
        Draw into a Cell, only called for column of type LV_USER
        """
        geUserArea = drawinfo["frame"]
        ypos = drawinfo["ypos"]
        if col == 5:
            if obj.bLoaded:
                geUserArea.DrawBitmap(self.IconLoaded, 20, ypos, 15, 15, 0, 0, 15, 15, c4d.BMP_NORMAL | c4d.BMP_ALLOWALPHA)
            if obj.MaterialInfo != "":
                geUserArea.DrawBitmap(self.IconWarning, 20, ypos, 15, 15, 0, 0, 15, 15, c4d.BMP_NORMAL | c4d.BMP_ALLOWALPHA)
        else:
            name = obj.MaterialName
            w = geUserArea.DrawGetTextWidth(name)
            h = geUserArea.DrawGetFontHeight()
            xpos = drawinfo["xpos"]
            ypos += drawinfo["height"]
            if obj.IsActive: fg=18
            else: fg=2
            geUserArea.DrawSetTextCol(fg=fg, bg=bgColor) # 18 for selection
            geUserArea.DrawText(name, xpos+14, int(ypos - (h * 1.1)))

    def DoubleClick(self, root, userdata, obj, col, mouseinfo):
        for tex in self.listOfTexture:
            tex.Deselect()
            #dialog.RemoveFromMaterialList(tex)
        obj.Select()
        #dialog.AddToMaterialList(obj)
        dialog._treegui.Refresh()
        return True

    def DeletePressed(self, root, userdata):
        "Called when a delete event is received."
        for tex in reversed(self.listOfTexture):
            if tex.IsSelected:
                self.listOfTexture.remove(tex)

    def SelectAll(self, State):
        for tex in self.listOfTexture:
            if State:
                tex.Select()
                #dialog.AddToMaterialList(tex)
            else:
                tex.Deselect()
                #dialog.RemoveFromMaterialList(tex)
        dialog.UpdateUI(UpdateType="MaterialsToLoad")

    def CountSelected(self):
        SelectedCount = 0
        for tex in self.listOfTexture:
            if tex.IsSelected:
                SelectedCount += 1
        return SelectedCount


# Poliigon Material Converter class
class PoliigonMatConverterDlg(c4d.gui.GeDialog):

    # Variables
    BUTTON_CONVERT = 1000
    TEX_FOLDER = 1001
    RENDERER = 1002
    LIGHT_SETUP = 1005
    ADVANCED_SETTINGS = 1100
    INFO_TEXT = 1050
    SELECT_ALL = 1051
    CHECKBOX_IS_METAL = 2016

    mapDict = {}
    nMats = 0
    folderPath = ""
    PatchTransmission = True
    MaterialPreviewStatus = True
    bShowAdvnacedSettings = False

    ID_FOLDERPATH = 199
    ID_BTN_BROWSE = 200
    ID_BTN_RELOAD = 201
    ID_BTN_SAVE = 202
    ID_BTN_SEARCH = 203
    ID_BTN_PREVIEW = 204
    ID_BTN_CONVERT = 205
    ID_BTN_APPLY = 206

    ID_MAT_PREVIEW = 210
    ID_CGUI_SETTINGS = 211

    ID_BTN_SETTINGS = 5500
    ID_TOOLTIP_SETTINGS = 5501

    _treegui = None
    MaterialListTree = ListView()

    #folder = os.path.dirname(__file__)
    #if folder not in sys.path:
    #    sys.path.insert(0, folder)


    def __init__(self):
        global internal
        global PMCversion
        
        vC4D = sorted(list(set([str(vD).split('_')[0].lower() for vD in dir(c4d)])))
        
        self.Engines = [("Physical", 0)]
        for pE in [("Arnold", 1029988), ("Corona", 1030480), ("Octane", 1029525), ("Redshift", 1036219), ("V-Ray", 1019782), ("V-Ray", 1053272), ("ProRender", 1037639)] :
            if pE[0] in self.Engines :
                continue
            elif pE[0] in str(c4d.plugins.FindPlugin(pE[1])):
                self.Engines.append(pE)
        
        if internal:
            # Variables that's only needed in the internal version
            self.OBJlist = []
            self.LightSetups = {"<None>":None}
            self.LightSetups_i = [("<None>", 0)]
            self.ImportedLights = False
            self.SavePath = ""
            self.SceneName = ""
        
        self._area = MaterialPreview(None)
        self.MaterialPreviewBmp = c4d.bitmaps.BaseBitmap()
        self.MaterialPreviewBmpTmp = c4d.bitmaps.BaseBitmap()
        self.MaterialPreviewBmp.Init(42, 42)
        
        VersionConfig = ConfigParser.ConfigParser()
        VersionConfig.read(os.path.join(PLUGIN_PATH, "res", "version.ini"))
        PMCversion = VersionConfig.get("Version", "PluginVersion")
        
        print ('PMC : '+str(PMCversion))

    # ------------------------- #
    #       User Interface      #
    # ------------------------- #

    def add_settings_button(self):
        if self.GroupBeginInMenuLine():  # always True, purpose indentation
            bc = c4d.BaseContainer()

            bc.SetInt32(c4d.BITMAPBUTTON_IGNORE_BITMAP_WIDTH, False)
            bc.SetInt32(c4d.BITMAPBUTTON_IGNORE_BITMAP_HEIGHT, True)
            w = 32
            h = 16

            bc.SetBool(c4d.BITMAPBUTTON_BUTTON, True)
            bc.SetBool(c4d.BITMAPBUTTON_TOGGLE, False)

            tooltip = c4d.plugins.GeLoadString(self.ID_TOOLTIP_SETTINGS)
            bc.SetString(c4d.BITMAPBUTTON_TOOLTIP, tooltip)

            if c4d.GetC4DVersion() // 1000 >= 21:
                idIconPrefs = 1026694
            else:
                idIconPrefs = 1026693
            bc.SetInt32(c4d.BITMAPBUTTON_ICONID1, idIconPrefs)

            bitmapButton = self.AddCustomGui(self.ID_BTN_SETTINGS,
                                             c4d.CUSTOMGUI_BITMAPBUTTON,
                                             "",
                                             c4d.BFH_RIGHT | c4d.BFV_CENTER,
                                             w,
                                             h,
                                             bc)
        self.GroupEnd()

        return bitmapButton

    # Draw the layout
    def CreateLayout(self):
        TogglePMCExceptionHook(True)

      # Get the lightsetups
        if internal:
            self.getLightsetups()

            # Set the title of the window
            self.SetTitle("Internal Poliigon Material Converter (v"+PMCversion+")")
        else:
            try : PLUGIN_NAME = c4d.plugins.GeLoadString(1000)
            except : PLUGIN_NAME = "Poliigon Material Converter"
            self.SetTitle("%s (v%s)" %(PLUGIN_NAME, PMCversion))

        ScriptPath = os.path.split(__file__)[0]
        #ScriptPath = os.path.join(ScriptPath, "res", "images")

        #OpenFolderContainer = c4d.BaseContainer()
        #ReloadFolderContainer = c4d.BaseContainer()
        #SaveFolderContainer = c4d.BaseContainer()

        self.add_settings_button()

        self.GroupBegin(id=30, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, title="", cols=1, groupflags=0)
        self.GroupBorderSpace(10, 10, 10, 10)
        self.GroupSpace(0, 10)

        if internal:
            self.AddCheckbox(id=self.ADVANCED_SETTINGS+10, flags=c4d.BFH_LEFT, initw=560, inith=10, name="Textures are stored in a subfolder called \"Generic_Files\"")
            self.SetBool(id=self.ADVANCED_SETTINGS+10, value=True)

        # Textures Folder
        self.GroupBegin(id=50, flags=c4d.BFH_SCALEFIT, rows=1, title="", cols=4, groupflags=0)
        self.FOLDERPATH = self.AddEditText(self.ID_FOLDERPATH, flags=c4d.BFH_SCALEFIT, inith=15, initw=100)

        # Browse for a folderpath
        bc = c4d.BaseContainer()
        bc.SetBool(c4d.BITMAPBUTTON_TOGGLE, True)
        bc.SetBool(c4d.BITMAPBUTTON_BUTTON, True)
        bc.SetLong(c4d.BITMAPBUTTON_FORCE_SIZE, 22)
        bc.SetString(c4d.BITMAPBUTTON_TOOLTIP, c4d.plugins.GeLoadString(6004))
        BrowseFolderBtn = self.AddCustomGui(self.ID_BTN_BROWSE, c4d.CUSTOMGUI_BITMAPBUTTON, "Browse", c4d.BFH_RIGHT, 22, 10, bc)

        # Reload folderpath
        bc = c4d.BaseContainer()
        bc.SetBool(c4d.BITMAPBUTTON_TOGGLE, True)
        bc.SetBool(c4d.BITMAPBUTTON_BUTTON, True)
        bc.SetLong(c4d.BITMAPBUTTON_FORCE_SIZE, 22)
        bc.SetString(c4d.BITMAPBUTTON_TOOLTIP, c4d.plugins.GeLoadString(6005))
        self.ReloadFolderBtn = self.AddCustomGui(self.ID_BTN_RELOAD, c4d.CUSTOMGUI_BITMAPBUTTON, "Reload", c4d.BFH_RIGHT, 22, 10, bc)

        # Save folderpath as default
        bc = c4d.BaseContainer()
        bc.SetBool(c4d.BITMAPBUTTON_TOGGLE, True)
        bc.SetBool(c4d.BITMAPBUTTON_BUTTON, True)
        bc.SetLong(c4d.BITMAPBUTTON_FORCE_SIZE, 22)
        bc.SetString(c4d.BITMAPBUTTON_TOOLTIP, c4d.plugins.GeLoadString(6000))
        self.SaveFolderBtn = self.AddCustomGui(self.ID_BTN_SAVE, c4d.CUSTOMGUI_BITMAPBUTTON, "Save", c4d.BFH_RIGHT, 22, 10, bc)
        self.GroupEnd()


        # Info Text
        self.GroupBegin(id=51, flags=c4d.BFH_SCALEFIT, rows=2, title="", cols=1, groupflags=0)
        self.AddStaticText(id=self.INFO_TEXT, flags=c4d.BFH_SCALEFIT, initw=10, name=c4d.plugins.GeLoadString(2000))
        self.GroupEnd()

        # Renderer
        self.GroupBegin(id=52, flags=c4d.BFH_LEFT, rows=1, title="", cols=3, groupflags=0)
        self.AddStaticText(id=5, flags=c4d.BFH_LEFT, initw=120,inith=12, name=c4d.plugins.GeLoadString(2001))
        self.AddComboBox(id=self.RENDERER,flags=c4d.BFH_CENTER)
        if internal:
            self.AddButton(id=self.RENDERER+1, flags=c4d.BFH_LEFT, initw=70, inith=10, name="Get Active")
            self.AddCheckbox(id=self.ADVANCED_SETTINGS+6, flags=c4d.BFH_CENTER, initw=0, inith=12, name="All renderers")
        self.GroupEnd()

        # Light Setup
        if internal:
            self.GroupBegin(id=71, flags=c4d.BFH_LEFT, rows=2, title="", cols=3, groupflags=0)
            self.AddStaticText(id=5, flags=c4d.BFH_LEFT, initw=120,inith=35, name="Light Setup")
            self.AddComboBox(id=self.LIGHT_SETUP,flags=c4d.BFH_CENTER)
            i = 0
            for setup in self.LightSetups_i:
                self.AddChild(id=self.LIGHT_SETUP, subid=setup[1], child=setup[0])
                i+=1
            self.AddButton(id=self.LIGHT_SETUP+1, flags=c4d.BFH_LEFT, initw=100, inith=10, name="Open Folder")
            self.GroupEnd()

        # Materials List
        self.GroupBegin(id=53, flags=c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, rows=3, title="", cols=1)

        # Select All
        self.SelectAll = self.AddCheckbox(id=self.SELECT_ALL, flags=c4d.BFH_LEFT, initw=200, inith=10, name=c4d.plugins.GeLoadString(2015)) # Select All


        # List TreeView
        customgui = c4d.BaseContainer()
        customgui.SetBool(c4d.TREEVIEW_BORDER, c4d.BORDER_THIN_IN)
        customgui.SetBool(c4d.TREEVIEW_HAS_HEADER, False)
        customgui.SetBool(c4d.TREEVIEW_HIDE_LINES, False)
        customgui.SetBool(c4d.TREEVIEW_MOVE_COLUMN, False)
        customgui.SetBool(c4d.TREEVIEW_NO_MULTISELECT, False)
        customgui.SetBool(c4d.TREEVIEW_RESIZE_HEADER, False)
        customgui.SetBool(c4d.TREEVIEW_FIXED_LAYOUT, True)
        customgui.SetBool(c4d.TREEVIEW_ALTERNATE_BG, True)
        customgui.SetBool(c4d.TREEVIEW_CURSORKEYS, True)
        customgui.SetBool(c4d.TREEVIEW_NOENTERRENAME, False)
        self._treegui = self.AddCustomGui(5001, c4d.CUSTOMGUI_TREEVIEW, "", c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 100, 30, customgui)

        self.GroupEnd()


        self.GroupBegin(id=1234567, flags=c4d.BFH_SCALEFIT, rows=1, cols=3)


        # Material Preview
        self.AddUserArea(self.ID_MAT_PREVIEW, c4d.BFH_RIGHT, 42, 42)
        self.AttachUserArea(self._area, self.ID_MAT_PREVIEW)

        # Material Info Text
        self.GroupBegin(id=55, flags=c4d.BFH_SCALEFIT, rows=2, cols=1)
        self.MaterialNameLabel = self.AddStaticText(id=100035340, flags=c4d.BFH_SCALEFIT, initw=100, name="")
        self.MaterialInfoLabel = self.AddStaticText(id=105252000, flags=c4d.BFH_SCALEFIT, initw=100, name="")
        self.GroupEnd()


        self.GroupBegin(id=12345674, flags=c4d.BFH_RIGHT, rows=1, cols=1)

        # Search for the texture on Poliigon.com
        bc = c4d.BaseContainer()
        bc.SetBool(c4d.BITMAPBUTTON_TOGGLE, True)
        bc.SetBool(c4d.BITMAPBUTTON_BUTTON, True)
        bc.SetLong(c4d.BITMAPBUTTON_FORCE_SIZE, 22)
        bc.SetString(c4d.BITMAPBUTTON_TOOLTIP, c4d.plugins.GeLoadString(6003))
        self.BrowseMaterialBtn = self.AddCustomGui(self.ID_BTN_SEARCH, c4d.CUSTOMGUI_BITMAPBUTTON, "Bitmap Button", c4d.BFH_RIGHT, 22, 10, bc)

        # Toggle on/off Material Preview
        #self.BC_BTN_PREVIEW = c4d.BaseContainer()
        #self.BC_BTN_PREVIEW.SetBool(c4d.BITMAPBUTTON_TOGGLE, True)
        #self.BC_BTN_PREVIEW.SetBool(c4d.BITMAPBUTTON_BUTTON, True)
        #self.BC_BTN_PREVIEW.SetLong(c4d.BITMAPBUTTON_FORCE_SIZE, 22)
        #self.BC_BTN_PREVIEW.SetInt32(c4d.BITMAPBUTTON_BACKCOLOR, c4d.COLOR_BGFOCUS)
        #self.BC_BTN_PREVIEW.SetString(c4d.BITMAPBUTTON_TOOLTIP, c4d.plugins.GeLoadString(6002))
        #self.MaterialPreviewBtn = self.AddCustomGui(self.ID_BTN_PREVIEW, c4d.CUSTOMGUI_BITMAPBUTTON, "", c4d.BFH_RIGHT, 22, 10, self.BC_BTN_PREVIEW)
        self.GroupEnd()

        self.GroupEnd()


        # Advanced Settings
        self.GroupBegin(id=12345, flags=c4d.BFH_SCALEFIT, rows=5, cols=1)
        self.GroupSpace(0, 0)

        # Title Bar
        bc = c4d.BaseContainer()
        bc.SetBool(c4d.QUICKTAB_BAR, True)
        bc.SetString(c4d.QUICKTAB_BARTITLE, 'Advanced Settings')
        bc.SetBool(c4d.QUICKTAB_BARSUBGROUP, True)
        bc.SetInt32(c4d.QUICKTAB_BGCOLOR, c4d.COLOR_BG_GROUPBAR1)
        Adv_Settings_Bar = self.AddCustomGui(self.ID_CGUI_SETTINGS, c4d.CUSTOMGUI_QUICKTAB, '', c4d.BFH_SCALEFIT, 10, 13, bc)
        Adv_Settings_Bar.Select(0, True)
        self.bShowAdvnacedSettings = False

        # Settings
        self.GroupBegin(id=self.ADVANCED_SETTINGS, flags=c4d.BFH_SCALEFIT, rows=5, cols=1)#, title=c4d.plugins.GeLoadString(2003))
        self.GroupBorderNoTitle(c4d.BORDER_THIN_IN)
        self.GroupBorderSpace(5,5,5,8)
        if internal:
            self.AddCheckbox(id=self.ADVANCED_SETTINGS+7, flags=c4d.BFH_CENTER, inith=10, initw=450, name="Ask for scene name")
        self.AddCheckbox(id=self.ADVANCED_SETTINGS+1, flags=c4d.BFH_CENTER, initw=455, inith=10, name=c4d.plugins.GeLoadString(2004))
        self.AddCheckbox(id=self.ADVANCED_SETTINGS+2, flags=c4d.BFH_CENTER, initw=450, inith=10, name=c4d.plugins.GeLoadString(2005))
        self.AddCheckbox(id=self.ADVANCED_SETTINGS+4, flags=c4d.BFH_CENTER, initw=450, inith=10, name=c4d.plugins.GeLoadString(2006))
        self.AddCheckbox(id=self.ADVANCED_SETTINGS+3, flags=c4d.BFH_CENTER, initw=450, inith=10, name=c4d.plugins.GeLoadString(2007))
        self.AddCheckbox(id=self.ADVANCED_SETTINGS+5, flags=c4d.BFH_CENTER, initw=450, inith=10, name=c4d.plugins.GeLoadString(2008))
        self.GroupEnd()

        self.GroupEnd()

        self.AddCheckbox(id=self.CHECKBOX_IS_METAL, flags=c4d.BFH_LEFT, initw=0, inith=10, name=c4d.plugins.GeLoadString(2016))

        self.GroupEnd()

        # Convert
        self.GroupBegin(id=54, flags=c4d.BFH_SCALEFIT | c4d.BFV_BOTTOM, rows=2, cols=1)
        self.GroupSpace(0, 0)
        self.BUTTON_CONVERT = self.AddButton(id=self.ID_BTN_CONVERT, flags=c4d.BFH_SCALEFIT | c4d.BFV_BOTTOM, initw=100, inith=30, name=c4d.plugins.GeLoadString(2010))
        self.BUTTON_APPLYMAT = self.AddButton(id=self.ID_BTN_APPLY, flags=c4d.BFH_SCALEFIT | c4d.BFV_BOTTOM, initw=100, inith=20, name=c4d.plugins.GeLoadString(2011))
        self.GroupEnd()


        BrowseFolderBtn.SetImage(os.path.join(PLUGIN_PATH, "res", "images", "poliigon_pathBrowse.png"), False)
        self.ReloadFolderBtn.SetImage(os.path.join(PLUGIN_PATH, "res", "images", "poliigon_pathRefresh.png"), False)
        self.SaveFolderBtn.SetImage(os.path.join(PLUGIN_PATH, "res", "images", "poliigon_pathSave.png"), False)
        self.BrowseMaterialBtn.SetImage(os.path.join(PLUGIN_PATH, "res", "images", "poliigon_icon.png"), False)
        #self.MaterialPreviewBtn.SetImage(os.path.join(ImagesPath, "poliigon_materialPreview.png"), False)
        #self.MaterialPreview.SetImage(os.path.join(ImagesPath, "poliigon_pathSave.png"), False)

        for engine in self.Engines:
            self.AddChild(id=self.RENDERER, subid=engine[1], child=engine[0])
        self.SetInt32(id=self.RENDERER, value=self.getEngine())

        # Disable some features
        self.Enable(self.BUTTON_CONVERT, False)
        self.Enable(self.BUTTON_APPLYMAT, False)
        self.Enable(self.SelectAll, False)
        self.Enable(self.ID_BTN_PREVIEW, False)
        self.Enable(self.ID_BTN_SEARCH, False)
        self.Enable(self.ID_BTN_SAVE, False)
        self.Enable(self.ID_BTN_RELOAD, False)

        # Hide Elements
        self.HideElement(self.ADVANCED_SETTINGS, True)
        self.HideElement(self.ID_MAT_PREVIEW, True)

        # Default Bool Values
        self.SetBool(id=self.SelectAll, value=True)

        # Update the advanced settings
        if self.GetLong(self.RENDERER) in [0, 1029525, 1030480]:
            self.Enable(self.ADVANCED_SETTINGS+3, False)
        else:
            self.Enable(self.ADVANCED_SETTINGS+3, True)

        self.PostLoadUI()

        TogglePMCExceptionHook(False)

        return True

    def PostLoadUI(self):
        # Config File
        self.CONFIG = ConfigParser.ConfigParser()
        #self.CONFIG.optionxform = str
        #self.ConfigFilepath = os.path.join(PLUGIN_PATH, "res", "Settings.ini")
        self.ConfigFilepath = os.path.join(c4d.storage.GeGetC4DPath(8), "plugins",  "Poliigon Material Converter", "res", "Settings.ini")
        if os.path.exists(self.ConfigFilepath):
            self.CONFIG.read(self.ConfigFilepath)
        else:
            self.CONFIG.add_section('UserSettings')
            self.CONFIG.add_section('AdvancedSettings')

            # Check if user has installed plugin under programs
            try:
                self.ConfigFile('UserSettings', 'SavedFolderPath', '')
            except:
                # User has installed the plugin in the programs folder and lack permission
                PluginPath = os.path.join(c4d.storage.GeGetC4DPath(8), "plugins")
                PluginPath = os.path.join(PluginPath, "Poliigon Material Converter")
                try : PluginPath = PluginPath.decode("utf-8")
                except : pass
                if not os.path.exists(PluginPath):
                    os.makedirs(PluginPath)
                PluginPath = os.path.join(PluginPath, "res")
                if not os.path.exists(PluginPath):
                    os.makedirs(PluginPath)
                self.ConfigFilepath = os.path.join(PluginPath, "Settings.ini")
                with open(self.ConfigFilepath, 'w') as configfile:
                    self.CONFIG.write(configfile)
                self.ConfigFile('UserSettings', 'SavedFolderPath', '')

            self.ConfigFile("UserSettings", "materialpreview", "True")
            for i in [1,2,4]:
                self.ConfigFile("AdvancedSettings", str(self.ADVANCED_SETTINGS+i), True)


        self.MaterialListTree.listOfTexture = []
        TextureFolderPath = self.DefaultFolderPath(q=True)
        if TextureFolderPath:
            self.TextureFolder(TextureFolderPath)
            self.DefaultFolderPath(reverse=True)
        self._treegui.Refresh()

        # Load advanced settings
        for i in range(1, 8):
            CheckboxValue = self.ConfigFile("AdvancedSettings", str(self.ADVANCED_SETTINGS+i))
            self.SetBool(self.ADVANCED_SETTINGS+i, (CheckboxValue == "True"))

    # Update the UI
    def UpdateUI(self, UpdateType, Data=None):

        # Texture Folder
        if UpdateType == "TexturesFolder":
            self.SetString(self.FOLDERPATH, Data)
            self.Enable(self.SelectAll, (self.nMats > 0))
            if self.nMats > 1:
                msg = c4d.plugins.GeLoadString(2014)
                msg = msg.replace("0", str(self.nMats))
            elif self.nMats == 1:
                msg = c4d.plugins.GeLoadString(2013)
            else:
                msg = c4d.plugins.GeLoadString(2012)
            self.SetString(self.INFO_TEXT, msg)

        elif UpdateType == "MaterialsToLoad":
            NMatsToLoad = self.MaterialListTree.CountSelected()
            self.Enable(self.BUTTON_CONVERT, (NMatsToLoad > 0))
            if NMatsToLoad == 1:
                LoadMsg = c4d.plugins.GeLoadString(2009)
            else:
                LoadMsg = c4d.plugins.GeLoadString(2010)
                LoadMsg = LoadMsg.replace("0", str(NMatsToLoad))
            self.SetString(self.BUTTON_CONVERT, LoadMsg)

            # Toggle on/off select all
            if NMatsToLoad == 0:
                self.SetBool(self.SELECT_ALL, False)
            elif NMatsToLoad == self.nMats:
                self.SetBool(self.SELECT_ALL, True)

        elif UpdateType == "ToggleAdvancedSettings":
            self.HideElement(self.ADVANCED_SETTINGS, self.bShowAdvnacedSettings)
            self.LayoutChanged(30)
            self.bShowAdvnacedSettings = not self.bShowAdvnacedSettings

        elif UpdateType == "ToggleMaterialButton":
            self.Enable(self.ID_BTN_PREVIEW, Data)
            self.Enable(self.ID_BTN_SEARCH, Data)

        elif UpdateType == "ToggleFolderButtons":
            self.Enable(self.ID_BTN_SAVE, Data)
            self.Enable(self.ID_BTN_RELOAD, Data)

    def InitValues(self):
        # Initialize the column layout for the TreeView.
        layout = c4d.BaseContainer()
        layout.SetLong(4, c4d.LV_CHECKBOX)
        layout.SetLong(6, c4d.LV_USER)
        layout.SetLong(5, c4d.LV_USER)
        self._treegui.SetLayout(3, layout)

        # Set the header titles.
        self._treegui.SetHeaderText(4, "Load")
        self._treegui.SetHeaderText(5, "Material Name")
        #self._treegui.SetHeaderText(6, "")
        self._treegui.Refresh()

        # Set TreeViewFunctions instance used by our CUSTOMGUI_TREEVIEW
        self._treegui.SetRoot(self._treegui, self.MaterialListTree, None)

        if self.GetLong(self.RENDERER) == 1036219:  # if Redshift
            self.Enable(self.CHECKBOX_IS_METAL, True)
        else:
            self.Enable(self.CHECKBOX_IS_METAL, False)

        return True

    # ----------------------- #
    #       Functions         #
    # ----------------------- #

    # Get the active render engine and set it as default in the dropdown
    def getEngine(self):
        doc = c4d.documents.GetActiveDocument()
        RenderEngine = doc.GetActiveRenderData()[c4d.RDATA_RENDERENGINE]
        if RenderEngine == 1023342: RenderEngine = 0 # Physical
        return RenderEngine

    def Command(self, id, msg):
        TogglePMCExceptionHook(True)
        # BUTTON: CONVERT!
        if id==self.ID_BTN_CONVERT:
            self.Convert()

        # BUTTON: Textures Folder ...
        elif id==self.ID_BTN_BROWSE:
            self.BrowseTexturesFolder()

        # Update UI
        elif id == self.RENDERER or id == self.RENDERER+1: # Update UI
            if id==self.RENDERER+1: # Update UI
                self.SetInt32(self.RENDERER, self.getEngine())
            if self.GetLong(self.RENDERER) in [0, 1029525, 1030480, 1037639]:
                self.Enable(self.ADVANCED_SETTINGS+3, False)
            else: #if self.GetLong(self.RENDERER) in [1029988, 1036219, 1019782]:
                self.Enable(self.ADVANCED_SETTINGS+3, True)
            self.TextureFolder(self.GetString(self.ID_FOLDERPATH))

            self.InitValues()

        elif id == self.ID_CGUI_SETTINGS:
            self.UpdateUI("ToggleAdvancedSettings")

        elif id==1:
            if self.GetString(self.ID_FOLDERPATH) != self.folderPath or self.GetString(self.ID_FOLDERPATH) == "":
                self.TextureFolder(self.GetString(self.ID_FOLDERPATH))

        elif id==self.SELECT_ALL:
            self.MaterialListTree.SelectAll(self.GetBool(self.SelectAll))
            self._treegui.Refresh()

        # Refresh Folder
        elif id == self.ID_BTN_RELOAD:
            self.TextureFolder(self.GetString(self.ID_FOLDERPATH))

        # Save / Revert folderpath
        elif id == self.ID_BTN_SAVE:
            self.DefaultFolderPath(set=True)

        # Browse Material
        elif id == self.ID_BTN_SEARCH:
            self.browseMaterial()

        # Material Preview
        elif id == self.ID_BTN_PREVIEW:
            self.ToggleMaterialPreview()

        # Open light_setups folder (internal only)
        elif id==self.LIGHT_SETUP+1:
            self.openFolder()

        elif id == self.ID_BTN_APPLY:
            self.ApplyMaterialToSelection(self.GetString(self.MaterialNameLabel))

        elif id in range(self.ADVANCED_SETTINGS+1, self.ADVANCED_SETTINGS+8):
            self.ConfigFile('AdvancedSettings', str(id), self.GetBool(id))

        elif id == self.ID_BTN_SETTINGS:
            dlg_settings = PMCSettings.get_dialog()
            if dlg_settings is None:
                PMCSettings.__res__ = __res__
                PMCSettings.main()
            elif dlg_settings.IsOpen():
                dlg_settings.Close()
            else:
                dlg_settings.Open(dlgtype=c4d.DLG_TYPE_ASYNC,
                                  pluginid=PLUGIN_ID,
                                  defaultw=360,
                                  defaulth=380,
                                  subid=1)

        TogglePMCExceptionHook(False)

        return True

    def ConfigFile(self, Category, Setting, DataToWrite = None):
        if DataToWrite == None:
            try : return self.CONFIG.get(Category, Setting)
            except : return False
        
        self.CONFIG.set(Category, str(Setting), str(DataToWrite))
        
        # Write data to file
        try : 
            with open(self.ConfigFilepath, 'w') as configfile:
                self.CONFIG.write(configfile)
        except : pass
        
        # Refresh config file
        try :
            self.CONFIG.read(self.ConfigFilepath)
        except : pass

    # ----------------------- #
    #     Textures Folder     #
    # ----------------------- #

    def DefaultFolderPath(self, q=False, set=False, reverse=False, default=False):
        # Query the currently saved filepath
        if q:
            return self.ConfigFile('UserSettings', 'SavedFolderPath')

        # Save current filepath as default
        elif set:
            if self.ConfigFile('UserSettings', 'SavedFolderPath') == self.GetString(self.ID_FOLDERPATH):
                default = True
                self.ConfigFile('UserSettings', 'SavedFolderPath', '')
                self.UpdateUI("TexturesFolder", "")
                self.UpdateUI("ToggleFolderButtons", False)
                self.MaterialListTree.listOfTexture = []
                self._treegui.Refresh()
                self.Enable(self.SELECT_ALL, False)
                self.UpdateMaterialSelection(False)
            else:
                self.ConfigFile('UserSettings', 'SavedFolderPath', self.GetString(self.ID_FOLDERPATH))
                reverse = True

        # Apply the reverse icon to the button
        ImagesPath = os.path.join(PLUGIN_PATH, "res", "images")
        if reverse:
            self.SaveFolderBtn.SetImage(os.path.join(ImagesPath, "poliigon_pathRevert.png"), False)

        # Apply the default icon to the button
        elif default:
            self.SaveFolderBtn.SetImage(os.path.join(ImagesPath, "poliigon_pathSave.png"), False)

    def BrowseTexturesFolder(self):
        folderPath = c4d.storage.LoadDialog(title=c4d.plugins.GeLoadString(2000), flags=2)
        if folderPath == None: # Return if user cancels
            return
        try : folderPath = folderPath.decode("utf-8")
        except : pass
        self.TextureFolder(folderPath)

    # BUTTON: Textures Folder "..."
    def TextureFolder(self, folderPath):

        if folderPath == self.DefaultFolderPath(q=True):
            self.DefaultFolderPath(reverse = True)
        else:
            self.DefaultFolderPath(default = True)

        if not folderPath or not os.path.isdir(folderPath):
            self.UpdateUI("ToggleFolderButtons", False)
            if not folderPath:
                self.SetString(self.INFO_TEXT, c4d.plugins.GeLoadString(2000))
            else:
                self.SetString(self.INFO_TEXT, c4d.plugins.GeLoadString(2002))
            return False

        # If Generic_Files = True, just add it to the folderpath. (internal only)
        if internal and self.GetBool(id=self.ADVANCED_SETTINGS+10):
            folderPath = os.path.join(folderPath, "Generic_Files")

        # Update ui with a spinning loadingbar, to let the user know the converter is working
        c4d.StatusSetSpin()
        c4d.StatusSetText(("%s %s" %(c4d.plugins.GeLoadString(3002), folderPath)))

        # Search folder for poliigon textures & models
        self.mapDict = self.getTextures(folderPath)

        self.matsFound = copy.deepcopy(self.mapDict)

        # Check if materials are valid
        self.mapDict, self.nMats = self.checkTextures(self.mapDict)

        self.folderPath = folderPath

        self.UpdateMaterialSelection(False)

        self.populateMaterialList()

        if internal:
            if self.GetBool(id=self.ADVANCED_SETTINGS+10):

                folderPath = folderPath.replace("Generic_Files", "")
        self.UpdateUI("TexturesFolder", folderPath)
        self.UpdateUI("MaterialsToLoad")
        self.UpdateUI("ToggleFolderButtons", True)
        #self.SetBool(self.SELECT_ALL, True)


        # All the heavy work has now been done, clear the status bar
        c4d.StatusClear()

    # Search through the directory and sort all textures in a dictionary
    def getTextures(self, path):
        mapDict = {}
        self.previewImages = {}
        previewTypes = ["_Cube", "_Flat", "_Sphere"]
        supportedMaps = ["COL_", "AO_", "DISP_", "GLOSS_", "NRM_", "NRM16_", "DISP16_", "REFL_", "ROUGHNESS_", "ALPHAMASKED_", "MASK_", "TRANSMISSION_", "SSS_", "METALNESS_"] + previewTypes
        supportedExtentions = ['.jpg', '.tif', '.png', '.obj']
        if internal:
            self.OBJlist = []
            supportedExtentions += ['.fbx', '.FBX']

        # Search the directory for textures and models
        for root, dirs, files in os.walk(path):
            for name in files:
                if os.path.splitext(name)[1] in supportedExtentions: # Check for any supported image files or models
                    # If a model is found, add it to the obj list (internal only)
                    if internal:
                        if os.path.splitext(name)[1] == '.obj' or os.path.splitext(name)[1] == '.fbx' or os.path.splitext(name)[1] == '.FBX':
                            self.OBJlist.append(os.path.join(root, name))
                    # Check if the filename contains a keyword from supportedMaps, if so we can assume it's a poliigon texture
                    for Map in supportedMaps:
                        if Map in name:
                            # Get some info about the texture, such as material name & resolution
                            # Poliigon's naming convention: MaterialName_MapType_Resolution_Workflow.FileExtention
                            # Example:
                            # WoodenPlanks001_COL_3K.jpg
                            # MetalWorn003_NRM_1K_SPECULAR.png (workflow only applies when it's a metal material)
                            fname, ext = os.path.splitext(name)
                            FileSplit = fname.split("_")
                            MatName = FileSplit[0]
                            res = FileSplit[len(FileSplit)-1]

                            # Check if it's a preview
                            if Map in previewTypes:
                                if MatName not in self.previewImages:
                                    self.previewImages[MatName] = {}
                                self.previewImages[MatName][Map] = os.path.join(root, name)
                                continue

                            # Get workflow and add to dict
                            # This is needed to determain if we're loading a metal material or a dialectric
                            workflow = "DIALECTRIC"
                            if res == "SPECULAR" or res == "METALNESS":
                                #workflow = res
                                res = FileSplit[len(FileSplit)-2]
                            if workflow not in mapDict:
                                mapDict[workflow] = {}

                            # Add Resolution in dict
                            if res not in mapDict[workflow]:
                                mapDict[workflow][res] = {}

                            # Add material in dict
                            if MatName not in mapDict[workflow][res]:
                                mapDict[workflow][res][MatName] = {}
                            
                            # Add texture path to dict
                            if Map not in mapDict[workflow][res][MatName]:
                                try : mapDict[workflow][res][MatName][Map] = str(os.path.join(root, name))
                                except :
                                    try : mapDict[workflow][res][MatName][Map] = (os.path.join(root, name)).encode('utf-8')
                                    except : pass


                        # The dict may end up looking something like this:
                        # {"DIALECTRIC":{
                        #    "3K":{
                        #        "WoodenPlanks001":{
                        #            "COL_" : "C:\WoodenPlanks001_COL_4K.jpg"
                        #            "GLOSS_" : "C:\WoodenPlanks001_GLOSS_4K.jpg"
                        #            "REFL_" : "C:\WoodenPlanks001_REFL_4K.jpg"
                        #            "NRM_" : "C:\WoodenPlanks001_NRM_4K.jpg"
                        #        }
                        #    }
                        #}}

        
        #print(mapDict.keys())
        #print(json.dumps(mapDict,indent=1))
        return(mapDict)

    # Check for any invalid materials, if found give the user a warning prompt
    def checkTextures(self, mapDict):
        # Each material must contain at least 4 of the required maps
        requiredMaps = ["COL_", "GLOSS_", "REFL_", "NRM_", "ALPHAMASKED_"]
        if c4d.documents.GetActiveDocument().GetActiveRenderData()[c4d.RDATA_RENDERENGINE] == 1053272 : requiredMaps += ["ROUGHNESS_","METALNESS_"]
        nMats = 0
        MissingMaterials = []
        MatsToRemove = []
        for workflow in mapDict:
            for res in mapDict[workflow]:
                for mat in mapDict[workflow][res]:
                    MissingMaps = []

                    # If an alphamasked map exists, add it as the color map too
                    if "ALPHAMASKED_" in mapDict[workflow][res][mat]:
                        mapDict[workflow][res][mat]["COL_"] = mapDict[workflow][res][mat]["ALPHAMASKED_"]
                        self.matsFound[workflow][res][mat]["COL_"] = mapDict[workflow][res][mat]["ALPHAMASKED_"]

                    if workflow == 'SPECULAR' :
                        for map in ["GLOSS_", "REFL_", "COL_"]:
                            # If a required map is missing add it to the MissingMaps list
                            if map not in self.matsFound[workflow][res][mat]:
                                MissingMaps.append(map[:-1])
                                mapDict[workflow][res][mat][map] = ""
                                self.matsFound[workflow][res][mat][map] = ""
                    elif workflow == 'METALNESS' :
                        for map in ["ROUGHNESS_", "METALNESS_", "COL_"]:
                            # If a required map is missing add it to the MissingMaps list
                            if map not in self.matsFound[workflow][res][mat]:
                                MissingMaps.append(map[:-1])
                                mapDict[workflow][res][mat][map] = ""
                                self.matsFound[workflow][res][mat][map] = ""
                    elif workflow == 'DIALECTRIC' :
                        for map in ["GLOSS_", "COL_"]:
                            # Based on:
                            # https://bitbucket.org/TheDuckCow/poliigon-material-converter/src/02fe9f2c66b745d1dd9895ff92e87fab7a5331af/poliigon_converter.py?atlOrigin=eyJpIjoiMWRiZjlmZjhkYmE3NDg0Mzk3NWI3ODZhZjczNGQyODQiLCJwIjoiYmItY2hhdHMtaW50ZWdyYXRpb24ifQ#lines-589
                            # NOTE: NRM maps are handleed below and ALPHAMASKED
                            #       has already replaced COL map above.
                            # If a required map is missing add it to the MissingMaps list
                            if map not in self.matsFound[workflow][res][mat]:
                                MissingMaps.append(map[:-1])
                                mapDict[workflow][res][mat][map] = ""
                                self.matsFound[workflow][res][mat][map] = ""

                    if "NRM_" not in self.matsFound[workflow][res][mat]:
                        # Check if 16 bit normal exists, and use that instead
                        if "NRM16_" in self.matsFound[workflow][res][mat]:
                            self.matsFound[workflow][res][mat]["NRM_"] = mapDict[workflow][res][mat]["NRM16_"]
                        else:
                            MissingMaps.append("NRM")
                            self.matsFound[workflow][res][mat]["NRM_"] = ""

                    # If one or more required maps were missing from the material, add it to the incomplete materials list
                    if len(MissingMaps) > 0:
                        mapstr = ""
                        for Map in MissingMaps:
                            mapstr += Map+", "
                        MissingMaterials.append(mat+"_"+res + "Missing Maps: "+mapstr[:-2]+"")
                        #
                        MatsToRemove.append([workflow, res, mat])

                    nMats+=1 # Count how many valid materials have been found.

        # Check for textures using the metalness workflow, and warn users
        if c4d.documents.GetActiveDocument().GetActiveRenderData()[c4d.RDATA_RENDERENGINE] != 1053272 : 
            if "METALNESS" in mapDict:
                for res in mapDict["METALNESS"]:
                    for mat in mapDict["METALNESS"][res]:
                        try:
                            # Check if it has an specular version too, then we don't have to warn
                            mapDict["SPECULAR"][res][mat]
                        except:
                            MissingMaterials.append(mat+"_"+res + "Metalness workflow is currently not supported.")

            # Remove invalid materials from the dictionary
            #for MatInfo in MatsToRemove:
                #del mapDict[MatInfo[0]][MatInfo[1]][MatInfo[2]]
            if "METALNESS" in mapDict:
                reses = []
                for res in mapDict["METALNESS"]:
                    reses.append(res)
                del mapDict["METALNESS"]
                mapDict["METALNESS"] = {}
                for res in reses:
                    mapDict["METALNESS"][res] = {}

        self.MissingMaterials = MissingMaterials

        return mapDict, nMats

    # ----------------------- #
    #     Material List       #
    # ----------------------- #

    def populateMaterialList(self):
        doc = c4d.documents.GetActiveDocument()
        AllMaterials = doc.GetMaterials()
        ListOfMaterials = []
        IncompleteMaterials = []
        for workflow in self.matsFound:
            for res in self.matsFound[workflow]:
                for matn in self.matsFound[workflow][res]:

                    # Check if it's an invalid material
                    missingmat = matn not in self.mapDict[workflow][res]
                    #missingmat = False
                    #if workflow != "METALNESS":  #VRay5
                    #    if matn not in self.mapDict[workflow][res]:
                    #        missingmat = True
                    #else:
                    #    missingmat = True

                    # If material is valid, add it to the list.
                    materialName = matn+"_"+res

                    for mat in self.MissingMaterials:
                        if materialName in mat:
                            missingmat = True

                    #Item = TextureObject(materialName)
                    if not missingmat:
                        ListOfMaterials.append(materialName)
                    else:
                        IncompleteMaterials.append(materialName)


        ListOfMaterials = sorted(ListOfMaterials, key=lambda s: s.lower())
        IncompleteMaterials = sorted(IncompleteMaterials, key=lambda s: s.lower())
        ListOfMaterials += IncompleteMaterials
        self.MaterialListTree.listOfTexture = []
        for Mat in ListOfMaterials:
            Item = TextureObject(Mat)
            Item.MaterialName = Mat
            self.MaterialListTree.listOfTexture.append(Item)
            #if True in [x.GetName()==Mat for x in AllMaterials]:
            #    Item.bLoaded = True
            #    self.MaterialListTree.SetCheck(None, None, Item, None, False, None)
            #else:
            #  if Mat not in IncompleteMaterials:
            #      self.MaterialListTree.SetCheck(None, None, Item, None, True, None)
            if Mat in IncompleteMaterials:
                for MissingMap in self.MissingMaterials:
                    if Mat in MissingMap:
                        MaterialInfo = MissingMap.replace(Mat, "")
                        Item.MaterialInfo = MaterialInfo
            if len(ListOfMaterials) == 1:
                Item.IsActive = True
                self.UpdateMaterialSelection(Item)
        self._treegui.Refresh()

    # Search for the selcted material on Poliigon.com
    def browseMaterial(self):
        mat = self.GetString(self.MaterialNameLabel)
        try:
            import webbrowser
            import re
        except:
            return False
        # Construct the URL based on the material name
        url = mat.split('_')[0]
        url = re.sub("(?<=[a-z])(?=[A-Z])", "-", url)
        url = re.sub("(?<=[a-z])(?=[0-9])", "-", url)
        url = 'https://www.poliigon.com/texture/' + url
        url = url.lower()
        webbrowser.open(url, new=2)

        return True

    def ToggleMaterialPreview(self):
        self.HideElement(self.ID_MAT_PREVIEW, self.MaterialPreviewStatus)
        if self.MaterialPreviewStatus:
            self.BC_BTN_PREVIEW.SetInt32(c4d.BITMAPBUTTON_BACKCOLOR, c4d.COLOR_BGFOCUS)
        else:
            self.BC_BTN_PREVIEW.SetInt32(c4d.BITMAPBUTTON_BACKCOLOR, c4d.COLOR_BG_DARK2)
        self.LayoutChanged(30)


        self.MaterialPreviewStatus = not self.MaterialPreviewStatus
        self.UpdateMaterialPreview(self.GetString(self.MaterialNameLabel))

    def UpdateMaterialSelection(self, obj):
        if obj:
            self.UpdateMaterialPreview(obj.MaterialName)
            self.Enable(self.BUTTON_APPLYMAT, obj.bLoaded)
            self.SetString(self.MaterialNameLabel, obj.MaterialName)
            self.SetString(self.MaterialInfoLabel, obj.MaterialInfo)
            self.UpdateUI("ToggleMaterialButton", True)
            if obj.bLoaded:
                self.Enable(self.ID_BTN_APPLY, True)
        else:
            self.UpdateUI("ToggleMaterialButton", False)
            self.Enable(self.BUTTON_APPLYMAT, False)
            self.SetString(self.MaterialNameLabel, "")
            self.SetString(self.MaterialInfoLabel, "")
            self.UpdateMaterialPreview(False)
            self.UpdateUI("ToggleMaterialButton", False)

    def UpdateMaterialPreview(self, obj):
        ImgFilePath = None
        #self.UpdateUI("ToggleMaterialButton", True)
        #if self.MaterialPreviewStatus and obj:
        if obj and (self.ConfigFile("UserSettings", "materialpreview") == "True"):
            mat, res = obj.split("_")
            if mat in self.previewImages:
                for type in ["_Sphere", "_Cube", "_Flat"]:
                    if type in self.previewImages[mat]:
                        ImgFilePath = self.previewImages[mat][type]
                        break

            if not ImgFilePath:
              for workflow in self.matsFound:
                  if res in self.matsFound[workflow]:
                      if mat in self.matsFound[workflow][res]:
                          if "COL_" in self.matsFound[workflow][res][mat]:
                              ImgFilePath = self.matsFound[workflow][res][mat]["COL_"]
                              break

            if ImgFilePath:
                # Load the original Image
                #self.MaterialPreviewBmpTmp.InitWith(ImgFilePath.encode('utf-8'))
                self.MaterialPreviewBmpTmp.InitWith(p_Str(ImgFilePath))

                # Scale down the bitmap to 41x41
                if (self.MaterialPreviewBmpTmp.GetBw()-1 > 41 and self.MaterialPreviewBmpTmp.GetBh()-1 > 41):
                    self.MaterialPreviewBmpTmp.ScaleBicubic(self.MaterialPreviewBmp,
                     0, 0, self.MaterialPreviewBmpTmp.GetBw()-1, self.MaterialPreviewBmpTmp.GetBh()-1,
                     0, 0, 41, 41)
                else:
                    self.MaterialPreviewBmpTmp.ScaleIt(self.MaterialPreviewBmp, 256, True, False)

                # Apply the bitmap
                self._area.setBitmap(self.MaterialPreviewBmp)
                self._area.Redraw()

                # Flush the temp bitmap from memory
                self.MaterialPreviewBmpTmp.FlushAll()

                self.HideElement(self.ID_MAT_PREVIEW, False)
                self.LayoutChanged(30)
                return


        # Remove img
        self.HideElement(self.ID_MAT_PREVIEW, True)
        self.LayoutChanged(30)

    def ApplyMaterialToSelection(self, MaterialName):
        doc = c4d.documents.GetActiveDocument()
        Materials = doc.GetMaterials()
        for Mat in Materials:
            if Mat.GetName() == MaterialName:
                Objects = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)
                for Obj in Objects:
                    tag = Obj.GetTag(c4d.Ttexture)
                    if tag == None:
                        tag = c4d.TextureTag()
                        tag.SetMaterial(Mat)
                        Obj.InsertTag(tag)
                        tag[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW
                    else:
                        tag.SetMaterial(Mat)

                    if Mat.GetTypeName() == "Arnold Shader Network": # Arnold
                        m = self.getProjectScale()
                        tag = Obj.GetTag(1029989)
                        if not tag:
                            tag = c4d.BaseTag(1029989)
                            Obj.InsertTag(tag)
                            tag[486485632] = True
                            tag[1039494868] = (2*m)
                            tag[1635638890] = 1
                            tag[408131505] = 0

                    Obj.Message(c4d.MSG_UPDATE)
                    c4d.EventAdd()

    def Setloaded(self, MaterialName):
        for Mat in self.MaterialListTree.listOfTexture:
            if Mat.MaterialName == MaterialName:
                Mat.bLoaded = True
                #Mat.Deselect()
                #self.MaterialListTree.SetCheck(None, None, Mat, None, False, None)
        self._treegui.Refresh()

    # ----------------------- #
    #         Convert         #
    # ----------------------- #

    # CONVERT
    # Create materials out of all the valid texture sets
    # if internal: Also import models, save out the scenes + option to batch all engines
    def Convert(self):
        if not internal:
            self.LoadMaterials()
            return
        
        # Internal Pre Convert Operations
        if internal:
            self.ImportedLights = False

            # If multiple models are found, ask what to name the maya scene, or if the option ask_name = True (internal only)
            if len(self.OBJlist) > 1 or self.GetBool(id=self.ADVANCED_SETTINGS+7):
                self.SceneName = c4d.gui.RenameDialog('')#mc.promptDialog(query=True, text=True)
                if self.GetBool(id=self.ADVANCED_SETTINGS+10):
                    self.SavePath = os.path.join(self.folderPath, "..", "Cinema4D", self.SceneName+"_")
                else:
                    self.SavePath = os.path.join(self.folderPath,"Cinema4D",self.SceneName+"_")
            else:
                self.SceneName = os.path.basename(self.OBJlist[0])
                self.SceneName = os.path.splitext(self.SceneName)[0]
                if self.GetBool(id=self.ADVANCED_SETTINGS+10):
                    self.SavePath = os.path.join(self.folderPath, "..", "Cinema4D", self.SceneName+"_")
                else:
                    self.SavePath = os.path.join(self.folderPath,"Cinema4D", self.SceneName+"_")
        
        returnValue = False
        rEngine = self.GetLong(self.RENDERER)
        
        # Check if it should batch all render engines (internal only)
        if self.GetBool(id=self.ADVANCED_SETTINGS+6):
            # Arnold

            self.ImportedLights = False
            self.SetInt32(id=self.RENDERER, value=1029988)
            self.LoadMaterials()
            self.SaveFile('Arnold')

            # Octane
            self.ImportedLights = False
            self.SetInt32(id=self.RENDERER, value=1029525)
            self.LoadMaterials()
            self.SaveFile('Octane')

            # Corona
            self.ImportedLights = False
            self.SetInt32(id=self.RENDERER, value=1030480)
            self.LoadMaterials()
            self.SaveFile('Corona')

            # Redshift
            self.ImportedLights = False
            self.SetInt32(id=self.RENDERER, value=1036219)
            self.LoadMaterials()
            self.SaveFile('Redshift')

            # Vray
            self.ImportedLights = False
            try : self.SetInt32(id=self.RENDERER, value=1019782)
            except :
                try : self.SetInt32(id=self.RENDERER, value=1053272)
                except : pass
            self.LoadMaterials()
            self.SaveFile('Vray')
        
        else:
            # Create the materials for the selected render engine
            c4d.WriteConsole('LoadMaterials')
            self.LoadMaterials()
            
            # Save material
            if rEngine == 0: # Standard
                self.SaveFile('Physical')
            elif rEngine == 1029988: # Arnold
                self.SaveFile('Arnold')
            elif rEngine == 1029525: # Octane
                self.SaveFile('Octane')
            elif rEngine == 1030480: # Corona
                self.SaveFile('Corona')
            elif rEngine == 1036219: # Redshift
                 self.SaveFile('Redshift')
            elif rEngine in [1019782,111,1053272] : # Vray
                 self.SaveFile('Vray')
            elif rEngine == 1037639: # ProRenderer
                self.SaveFile('ProRenderer')
        
        # Clear the status bar
        c4d.StatusClear()
        c4d.gui.MessageDialog('All models loaded successfully.')

    def LoadMaterials(self):
        # Set the c4d statusbar to be spinning, showing that the converter is working...

        c4d.StatusSetSpin()

        rEngine = self.GetLong(self.RENDERER)
        MaterialsToLoad = self.MaterialListTree.GetAllChecked()
        mats = []
        for MatObj in MaterialsToLoad:

            c4d.StatusSetText('Loading Material: %s' % MatObj.MaterialName)

            Name, Res = MatObj.MaterialName.split("_")

            # Temp solution for finding workflow, will need to be changed when we add support for metalness
            # Workflow = MatObj.Workflow <- That would be best way of finding out workflow

            Workflow = None
            for Workflow_i in self.matsFound:
                if Workflow_i == 'METALNESS' and rEngine not in [1053272, 1029525]:
                    continue
                if Res in self.matsFound[Workflow_i]:
                    if Name in self.matsFound[Workflow_i][Res]:
                        Workflow = Workflow_i
                        break

            if Workflow is None:
                for Workflow_i in self.matsFound:
                    if Workflow is not None:
                        break
                    if Workflow_i == 'METALNESS' and rEngine not in [1053272, 1029525]:
                        continue
                    for Res in self.matsFound[Workflow_i]:
                        Res = Res[0]  # Should be singular, but one user encountered multiple values.
                        if Name in self.matsFound[Workflow_i][Res]:
                            Workflow = Workflow_i
                            break

            if Workflow is None:
                print('Could not determine Workflow for : %s' % MatObj.MaterialName)
                continue

            self.matsFound[Workflow][Res][Name]["Name"] = MatObj.MaterialName

            if internal:
                # Create the folder were everything will be saved and reconstruct the dictionary to use relative paths
                rEngineNames = {"1029988": "Arnold", "1029525": "Octane", "1030480": "Corona", "1036219": "Redshift", "1019782": "Vray", "1053272": "Vray", "111": "Vray"}
                matInfo2 = dict(self.matsFound[Workflow][Res][Name])
                matInfo = self.CreateFolder(matInfo2, MatObj.MaterialName, rEngineNames[str(rEngine)])
                doc = c4d.documents.GetActiveDocument()
                # Set the render engine to selected rEngine
                try: doc.GetActiveRenderData()[c4d.RDATA_RENDERENGINE] = rEngine
                except: return False
                c4d.EventAdd()

            # Convert Material
            Mat = 0
            if rEngine == 0:  # Standard
                Mat = self.createMaterial(self.matsFound[Workflow][Res][Name], Workflow, ProRenderer=False)
            elif rEngine == 1029988:  # Arnold
                Mat = self.createArnoldMaterial(self.matsFound[Workflow][Res][Name], Workflow)
            elif rEngine == 1029525:  # Octane
                Mat = self.CreateOctaneMat(self.matsFound[Workflow][Res][Name], Workflow)
            elif rEngine == 1030480:  # Corona
                Mat = self.CreateCoronaMat(self.matsFound[Workflow][Res][Name], Workflow)
            elif rEngine == 1036219:  # Redshift
                Mat = self.CreateRedshiftMat(self.matsFound[Workflow][Res][Name], Workflow)
            elif rEngine in [1019782, 111]:  # Vray
                Mat = self.CreateVrayMat(self.matsFound[Workflow][Res][Name], Workflow, "%s_%s" % (Name, Res))
            elif rEngine == 1053272:  # Vray5
                if 'METALNESS' in self.matsFound:
                    if Res in self.matsFound['METALNESS']:
                        if Name in self.matsFound['METALNESS'][Res]: Workflow = 'METALNESS'
                Mat = self.CreateVrayMat(self.matsFound[Workflow][Res][Name], Workflow, "%s_%s" % (Name, Res))
            elif rEngine == 1037639:  # ProRenderer
                Mat = self.createMaterial(self.matsFound[Workflow][Res][Name], Workflow, ProRenderer=True)

            if not Mat:
                c4d.gui.MessageDialog(c4d.plugins.GeLoadString(3001), type=c4d.GEMB_ICONEXCLAMATION)
                c4d.StatusClear()
                return False

            # Post load
            Mat.SetName(MatObj.MaterialName)
            mats.append(Mat)

            if MatObj.MaterialName == self.GetString(self.MaterialNameLabel):
                self.Enable(self.ID_BTN_APPLY, True)

            # Update and add the material into the current document
            # mat.Update( True, True )
            doc = c4d.documents.GetActiveDocument()
            doc.InsertMaterial(Mat)

            # Internal Operations
            if internal:
                self.ImportModel(Mat, MatObj.MaterialName)
            else:
                MatObj.bLoaded = True
                MatObj.Deselect()

        if self.GetBool(id=self.ADVANCED_SETTINGS + 5):
            self.CreatePreviewSpheres(mats)

        self.UpdateUI("MaterialsToLoad")
        self.SetBool(id=self.SELECT_ALL, value=False)
        self._treegui.Refresh()

        # Clear the status
        c4d.StatusClear()

        # Redraw the window
        # rEngine != 1029988 and
        if rEngine != 1036219:
            c4d.EventAdd(c4d.EVENT_FORCEREDRAW)

        if not internal:
            c4d.gui.MessageDialog(c4d.plugins.GeLoadString(3000))

    # Conform UV Maps to image dimensions
    def ConformUVMap(self, path):
        u = 1.0
        v = 1.0
        image = c4d.bitmaps.BaseBitmap()
        #if image.InitWith((path).encode('utf-8'))[0] == c4d.IMAGERESULT_OK:
        if image.InitWith(p_Str(path))[0] == c4d.IMAGERESULT_OK:
            width, height = image.GetSize()
            if width != height:
                if width > height:
                    v = float(width)/height
                    u = 1
                else:
                    u = float(height)/width
                    v = 1
        image.FlushAll()
        return(u, v)

    # Get the scale of the project for accurate displacements values
    def getProjectScale(self):
        doc = c4d.documents.GetActiveDocument()
        unitData = doc[c4d.DOCUMENT_DOCUNIT]
        unitData = unitData.GetUnitScale()
        multiplier = 1
        UnitsList = [0, .00001, .01, 1, 10, 10000, 10000000, 1.0/160934.4, 1.0/91.44, 1.0/30.48, 1.0/2.54]
        multiplier = UnitsList[unitData[1]]
        multiplier = multiplier/unitData[0]
        return multiplier


    # ------------------------- #
    #       Arnold Shader       #
    # ------------------------- #

    def CreateArnoldShader(self, mat, ID, x, y):
        msg = c4d.BaseContainer()
        msg.SetInt32(1000, 1029)
        msg.SetInt32(2001, 1033990)
        msg.SetInt32(2002, ID)
        msg.SetInt32(2003, x)
        msg.SetInt32(2004, y)
        mat.Message(c4d.MSG_BASECONTAINER, msg)
        return msg.GetLink(2011)

    def SetBaseShader(self, mat, shader, rootPortId):
        msg = c4d.BaseContainer()
        msg.SetInt32(1000, 1033)
        msg.SetLink(2001, shader)
        msg.SetInt32(2002, 0)
        msg.SetInt32(2003, rootPortId)
        mat.Message(c4d.MSG_BASECONTAINER, msg)
        return msg.GetBool(2011)

    def AddConnection(self, mat, srcNode, dstNode, dstPortId, alpha=False):
        msg = c4d.BaseContainer()
        msg.SetInt32(1000, 1031)
        msg.SetLink(2001, srcNode)
        if alpha : msg.SetInt32(2002, 4)
        else : msg.SetInt32(2002, 0)
        msg.SetLink(2003, dstNode)
        msg.SetInt32(2004, dstPortId)
        mat.Message(c4d.MSG_BASECONTAINER, msg)
        return msg.GetBool(2011)

    def createArnoldMaterial(self, matInfo, workflow):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        multiplier = self.getProjectScale()
        # for workflow in mapDict:
        #     for res in mapDict[workflow]:
        #         for matn in mapDict[workflow][res]:

        # if internal:
        #    # Create the folder were everything will be saved and reconstruct the dictionary to use relative paths
        #    matInfo2 = dict(matInfo)
        #    matInfo = self.CreateFolder(matInfo2, matn, 'Arnold')
        #    doc = c4d.documents.GetActiveDocument()
        #    try: RenderEngine = doc.GetActiveRenderData()[c4d.RDATA_RENDERENGINE] = 1029988
        #    except: return False
        #    c4d.EventAdd()
        #else:
        doc = c4d.documents.GetActiveDocument()

        # Create the material
        try:
            mat = c4d.BaseMaterial(1033991)
        except:
            return False
        if mat is None:
            return False

        nodeList = []

        # Create root shader --------------------------------------------------

        standard = self.CreateArnoldShader(mat, 314733630, 500, 100)
        self.SetBaseShader(mat, standard, 537905099)
        if workflow == "DIALECTRIC":
            # standard.SetName(matn + " (Dielectric Material)")
            standard.GetOpContainerInstance().SetFloat(220096084, 1.6)  # IOR
        else:
            # standard.SetName(matn + " (Specular Workflow)")
            standard.GetOpContainerInstance().SetFloat(220096084, 100)  # IOR
        standard.GetOpContainerInstance().SetFloat(1182964519, 1)  # Base: Weight

        # Reflection ----------------------------------------------------------

        if "REFL_" in matInfo:
            REFL_Node = self.CreateArnoldShader(mat, 262700200, 0, 100)
            REFL_Node.SetName("REFLECTION")
            REFL_Node.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
            REFL_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["REFL_"])
            REFL_CC_Node = self.CreateArnoldShader(mat, 1211336267, 250, 100)
            REFL_CC_Node.SetName("INVERT REFLECTION")
            if workflow == "DIALECTRIC":
                REFL_CC_Node.GetOpContainerInstance().SetBool(1952672187, True)
            REFL_CC_Node.GetOpContainerInstance().SetFloat(1582985598, 0)  # Exposure

            self.AddConnection(mat, REFL_CC_Node, standard, 801517079)
        else:
            REFL_Node = None
            REFL_CC_Node = None

        # Color ---------------------------------------------------------------

        COL_Node = self.CreateArnoldShader(mat, 262700200, 0, 50)
        COL_Node.SetName("COLOR")
        COL_Node.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
        if "ALPHAMASKED_" in matInfo:
            COL_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["ALPHAMASKED_"])
        else :
            COL_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["COL_"])
        if workflow == "SPECULAR":
            COL_CC_Node = self.CreateArnoldShader(mat, 1211336267, 250, 50)
            COL_CC_Node.GetOpContainerInstance().SetFloat(1582985598, 1) # Exposure
            self.AddConnection(mat, COL_Node, COL_CC_Node, 2023242509)

        # AO ------------------------------------------------------------------

        if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS + 1):
            AO_Node = self.CreateArnoldShader(mat, 262700200, 0, 0)
            AO_Node.SetName("AO")
            AO_Node.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
            AO_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["AO_"])
            nodeList.append(AO_Node)
            COMP_Node = self.CreateArnoldShader(mat, 1118743992, 250, 10)
            self.AddConnection(mat, AO_Node, COMP_Node, 1458503193)
            if workflow == "DIALECTRIC":
                COMP_Node.SetName("COLOR + AO")
                if REFL_Node is not None and REFL_CC_Node is not None:
                    self.AddConnection(mat, REFL_Node, REFL_CC_Node, 2023242509)
                self.AddConnection(mat, COL_Node, COMP_Node, 1458503192)
                self.AddConnection(mat, COMP_Node, standard, 1044225467)
            else:
                COMP_Node.SetName("REFLECTION + AO")
                if REFL_Node is not None and REFL_CC_Node is not None:
                    self.AddConnection(mat, REFL_Node, REFL_CC_Node, 2023242509)
                self.AddConnection(mat, REFL_CC_Node, COMP_Node, 1458503192)
                if workflow == "SPECULAR":
                    self.AddConnection(mat, COL_CC_Node, standard, 1044225467)
                    self.AddConnection(mat, COMP_Node, standard, 801517079)
                else:
                    self.AddConnection(mat, COL_Node, standard, 1044225467)
            COMP_Node.GetOpContainerInstance().SetInt32(2109221783, 19)
        else:
            if workflow == "SPECULAR":
                self.AddConnection(mat, COL_CC_Node, standard, 1044225467)
            else:
                self.AddConnection(mat, COL_Node, standard, 1044225467)

            if REFL_Node is not None and REFL_CC_Node is not None:
                self.AddConnection(mat, REFL_Node, REFL_CC_Node, 2023242509)

        # Gloss ---------------------------------------------------------------

        GLOSS_Node = self.CreateArnoldShader(mat, 262700200, 0, 190)
        GLOSS_Node.SetName("GLOSS")
        GLOSS_Node.GetOpContainerInstance().SetString(868305056, "linear")  # Set Color space
        GLOSS_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["GLOSS_"])
        GLOSS_CC_Node = self.CreateArnoldShader(mat, 1211336267, 250, 190)
        GLOSS_CC_Node.SetName("INVERT GLOSS")
        GLOSS_CC_Node.GetOpContainerInstance().SetBool(1952672187, True)
        GLOSS_CC_Node.GetOpContainerInstance().SetFloat(1582985598, 0)  # Exposure
        self.AddConnection(mat, GLOSS_Node, GLOSS_CC_Node, 2023242509)
        self.AddConnection(mat, GLOSS_CC_Node, standard, 1876347704)

        # Gloss Multiply ------------------------------------------------------

        # GLOSS_Multi_Node = self.CreateArnoldShader(mat, 1172556210, 0, 230)
        # GLOSS_Multi_Node.GetOpContainerInstance().SetFloat(1531096251, 1)
        # GLOSS_Multi_Node.SetName("GLOSS ADJUST")
        # self.AddConnection(mat, GLOSS_Multi_Node, GLOSS_CC_Node, 797267837)

        # Refl Multiply -------------------------------------------------------

        REFL_Multi_Node = self.CreateArnoldShader(mat, 1172556210, 0, 140)
        if workflow == "DIALECTRIC":
            REFL_Multi_Node.GetOpContainerInstance().SetFloat(1531096251, .6)
        else:
            REFL_Multi_Node.GetOpContainerInstance().SetFloat(1531096251, 1)
        REFL_Multi_Node.SetName("REFL ADJUST")
        self.AddConnection(mat, REFL_Multi_Node, REFL_CC_Node, 797267837)

        # Normals -------------------------------------------------------------

        NRM_Node = self.CreateArnoldShader(mat, 262700200, 0, 280)
        NRM_Node.SetName("NORMALS")
        NRM_Node.GetOpContainerInstance().SetString(868305056, "linear")  # Set Color space
        if self.GetBool(id=self.ADVANCED_SETTINGS + 4) and "NRM16_" in matInfo:
            NRM_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["NRM16_"])
        else:
            NRM_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["NRM_"])
        NRM_Map_Node = self.CreateArnoldShader(mat, 1512478027, 250, 280)
        self.AddConnection(mat, NRM_Node, NRM_Map_Node, 2075543287)
        self.AddConnection(mat, NRM_Map_Node, standard, 244376085)

        # Displacement --------------------------------------------------------

        if self.GetBool(id=self.ADVANCED_SETTINGS + 2) and ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS + 4))):
            DISP_Node = self.CreateArnoldShader(mat, 262700200, 400, 350)
            DISP_Node.SetName("DISPLACEMENT")
            DISP_Node.GetOpContainerInstance().SetString(868305056, "linear")  # Set Color space
            nodeList.append(DISP_Node)
            if self.GetBool(id=self.ADVANCED_SETTINGS + 4) and "DISP16_" in matInfo:
                DISP_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["DISP16_"])
            else:
                DISP_Node.GetOpContainerInstance().SetFilename(1737748425, matInfo["DISP_"])
            NRM_DISP_Node = self.CreateArnoldShader(mat, 1270483482, 630, 300)
            NRM_DISP_Node.GetOpContainerInstance().SetFloat(748850620, 0.1)
            self.AddConnection(mat, DISP_Node, NRM_DISP_Node, 276937581)
            self.SetBaseShader(mat, NRM_DISP_Node, 537905100)

        # Mask/Alphamasked ----------------------------------------------------

        if "MASK_" in matInfo:
            print(matInfo["MASK_"])
            ALPHA_NODE = self.CreateArnoldShader(mat, 262700200, 250, 350)
            ALPHA_NODE.SetName("MASK")
            ALPHA_NODE.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
            ALPHA_NODE.GetOpContainerInstance().SetFilename(1737748425, matInfo["MASK_"])
            ALPHA_NODE.GetOpContainerInstance().SetBool(333361456, True)
            ALPHA_NODE.GetOpContainerInstance().SetInt32(424767676, 3)
            nodeList.append(ALPHA_NODE)
            self.AddConnection(mat, ALPHA_NODE, standard, 784568645)

        elif "ALPHAMASKED_" in matInfo:
            ALPHA_NODE = self.CreateArnoldShader(mat, 262700200, 0, 250)
            ALPHA_NODE.SetName("ALPHAMASKED")
            ALPHA_NODE.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
            ALPHA_NODE.GetOpContainerInstance().SetFilename(1737748425, matInfo["ALPHAMASKED_"])
            ALPHA_NODE.GetOpContainerInstance().SetBool(333361456, True)
            ALPHA_NODE.GetOpContainerInstance().SetInt32(424767676, 3)
            nodeList.append(ALPHA_NODE)
            self.AddConnection(mat, ALPHA_NODE, standard, 784568645)

        # Transmission --------------------------------------------------------

        if "TRANSMISSION_" in matInfo:
            TRANSMISSION_NODE = self.CreateArnoldShader(mat, 262700200, 0, 300)
            TRANSMISSION_NODE.SetName("TRANSMISSION")
            TRANSMISSION_NODE.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
            TRANSMISSION_NODE.GetOpContainerInstance().SetFilename(1737748425, matInfo["TRANSMISSION_"])
            self.AddConnection(mat, COL_Node, standard, 1738477460)
            self.AddConnection(mat, TRANSMISSION_NODE, standard, 1053345482)
            self.PatchTransmission = False

        # SSS -----------------------------------------------------------------

        if "SSS_" in matInfo:
            standard.GetOpContainerInstance().SetFloat(639969601, 0.1)
            standard.GetOpContainerInstance().SetFloat(657869786, 0.1)  # Scale
            standard.GetOpContainerInstance().SetFloat(110275456, 1)
            standard.GetOpContainerInstance().SetString(110275456, "diffusion")  # Type
            standard.GetOpContainerInstance().SetBool(1589331029, True)  # Caustics
            standard.GetOpContainerInstance().SetBool(1863588601, True)  # Exit to Background
            standard.GetOpContainerInstance().SetVector(276268506, c4d.Vector(.5 * multiplier, .5 * multiplier, .5 * multiplier))
            SSS_NODE = self.CreateArnoldShader(mat, 262700200, 250, 400)
            SSS_NODE.SetName("SSS")
            SSS_NODE.GetOpContainerInstance().SetString(868305056, "sRGB")  # Set Color space
            SSS_NODE.GetOpContainerInstance().SetFilename(1737748425, matInfo["SSS_"])
            self.AddConnection(mat, SSS_NODE, standard, 676401187)
            nodeList.append(SSS_NODE)

            SSS_NODE1 = self.CreateArnoldShader(mat, 262700200, 250, 450)
            SSS_NODE1.SetName("SSS1")
            SSS_NODE1.GetOpContainerInstance().SetString(868305056, "linear")  # Set Color space
            SSS_NODE1.GetOpContainerInstance().SetFilename(1737748425, matInfo["SSS_"])
            self.AddConnection(mat, SSS_NODE1, standard, 639969601)

        # Conform UV Maps -----------------------------------------------------

        if self.GetBool(id=self.ADVANCED_SETTINGS + 3):
            u, v = self.ConformUVMap(matInfo["COL_"])
            nodeList += [COL_Node, GLOSS_Node, NRM_Node]
            if REFL_Node is not None:
                nodeList += [REFL_Node]
            for node in nodeList:
                node[1165373167] = u
                node[1126237774] = v

        # Import the models (internal only)
        # if internal:
        #     self.ImportModel(mat, matn)

        # This was for a quick patch, can't fully remember what it does. Might be worth rewriting this a bit cleaner later
        self.PatchTransmission = True

        mat.SetName(pName)
        return mat

    # ------------------------- #
    #       Standard Shader     #
    # ------------------------- #

    def createMaterial(self, matInfo, workflow, ProRenderer):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        #doc = c4d.documents.GetActiveDocument()

        rEngine = 0
        multiplier = self.getProjectScale()
        #for workflow in mapDict:
        #    for res in mapDict[workflow]:
        #        for matn in mapDict[workflow][res]:


        doc = c4d.documents.GetActiveDocument()

        # Create the material
        # Check if it should use the new PBR material
        if ProRenderer:
            c4d.CallCommand(202520, 202520) # New PBR Material
            mat = doc.GetFirstMaterial()
            mat[c4d.MATERIAL_USE_COLOR] = True
        else:
            try:
                mat = c4d.BaseMaterial(c4d.Mmaterial)
            except:
                return False


        # COLOR & AO
        if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) == True:
            # Use an AO map
            Fusion_shader = c4d.BaseList2D(c4d.Xfusion)
            Fusion_shader.SetName("COLOR + AO")
            if "ALPHAMASKED_" in matInfo :
                if "MASK_" in matInfo and "SSS_" in matInfo :
                    self.Create_Bitmap(Fusion_shader, matInfo, "COL_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
                else :
                    self.Create_Bitmap(Fusion_shader, matInfo, "ALPHAMASKED_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
            else :
                self.Create_Bitmap(Fusion_shader, matInfo, "COL_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
            self.Create_Bitmap(Fusion_shader, matInfo, "AO_", "AMBIENT OCCLUSION", c4d.SLA_FUSION_BLEND_CHANNEL, False)
            Fusion_shader[c4d.SLA_FUSION_MODE] = 2019
            mat[c4d.MATERIAL_COLOR_TEXTUREMIXING] = 3
            mat[c4d.MATERIAL_COLOR_SHADER] = Fusion_shader
            mat.InsertShader(Fusion_shader)
        else:
            # Don't use an AO map, load only color
            if "ALPHAMASKED_" in matInfo :
                if "MASK_" in matInfo and "SSS_" in matInfo :
                    self.Create_Bitmap(mat, matInfo, "COL_", "COLOR", c4d.MATERIAL_COLOR_SHADER, False)
                else :
                    self.Create_Bitmap(mat, matInfo, "ALPHAMASKED_", "COLOR", c4d.MATERIAL_COLOR_SHADER, False)
            else :
                self.Create_Bitmap(mat, matInfo, "COL_", "COLOR", c4d.MATERIAL_COLOR_SHADER, False)


        # GLOSS and REFLECTION
        if not ProRenderer:
            Bases = [c4d.REFLECTION_LAYER_LAYER_DATA + c4d.REFLECTION_LAYER_LAYER_SIZE * 4]
        else:
            defaultBase = c4d.REFLECTION_LAYER_LAYER_DATA + c4d.REFLECTION_LAYER_LAYER_SIZE * 4
            base = c4d.REFLECTION_LAYER_LAYER_DATA + c4d.REFLECTION_LAYER_LAYER_SIZE * 5
            Bases = [defaultBase, base]

        for base in Bases:
            # Gloss
            mat[base + c4d.REFLECTION_LAYER_MAIN_DISTRIBUTION] = 3
            mat[base + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS] = 100
            for i in range(30,50):
                try:
                    mat[base + i] = 60
                except:
                    pass
            #mat[base + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESSREAL] = 60
            GlossShader = self.Create_Bitmap(mat, matInfo, "GLOSS_", "GLOSS", base + 40, True)
            # Load Reflection
            mat[base + c4d.REFLECTION_LAYER_MAIN_VALUE_REFLECTION] = 1

            if workflow == "DIALECTRIC":
                self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", base + c4d.REFLECTION_LAYER_MAIN_SHADER_REFLECTION, True)
                # IOR/Fresnel settings
                mat[base + c4d.REFLECTION_LAYER_FRESNEL_MODE] = 1
                mat[base + c4d.REFLECTION_LAYER_MAIN_VALUE_SPECULAR] = 0.6
                if ProRenderer:
                    mat[defaultBase + c4d.REFLECTION_LAYER_FRESNEL_MODE] = 1
                    mat[base + c4d.REFLECTION_LAYER_FRESNEL_MODE + 5] = 1.5
                    mat[defaultBase + c4d.REFLECTION_LAYER_FRESNEL_MODE + 5] = 1.5
                else:
                    mat[base + c4d.REFLECTION_LAYER_FRESNEL_MODE + 5] = 1.8 # IOR Value
                #c4d.REFLECTION_LAYER_COLOR_TEXTURE
            else:
                self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", base + c4d.REFLECTION_LAYER_MAIN_SHADER_REFLECTION, False)
                self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", base + c4d.REFLECTION_LAYER_COLOR_TEXTURE, False)
                mat[base + c4d.REFLECTION_LAYER_MAIN_VALUE_SPECULAR] = 1
                if ProRenderer:
                    mat[base + c4d.REFLECTION_LAYER_FRESNEL_MODE] = 0

            if ProRenderer:
                GlossShader[c4d.BITMAPSHADER_COLORPROFILE] = 1
                GlossShader[c4d.BITMAPSHADER_EXPOSURE] = .3
                mat[defaultBase + c4d.REFLECTION_LAYER_MAIN_DISTRIBUTION] = 3
                mat[defaultBase + c4d.REFLECTION_LAYER_MAIN_VALUE_ROUGHNESS] = 100
                mat[base + c4d.REFLECTION_LAYER_COLOR_COLOR] = c4d.Vector(1,1,1)
                mat[defaultBase + c4d.REFLECTION_LAYER_COLOR_COLOR] = c4d.Vector(1,1,1)


        # Normals
        mat[c4d.MATERIAL_USE_NORMAL] = True
        nrm_shader = c4d.BaseList2D(c4d.Xbitmap)
        if self.GetBool(id=self.ADVANCED_SETTINGS+4) == True and "NRM16_" in matInfo:
            try : nrm_shader[c4d.BITMAPSHADER_FILENAME] = (matInfo["NRM16_"]).encode('utf-8')
            except : nrm_shader[c4d.BITMAPSHADER_FILENAME] = matInfo["NRM16_"]
        else:
            try : nrm_shader[c4d.BITMAPSHADER_FILENAME] = (matInfo["NRM_"]).encode('utf-8')
            except : nrm_shader[c4d.BITMAPSHADER_FILENAME] = matInfo["NRM_"]
        mat[c4d.MATERIAL_NORMAL_SHADER] = nrm_shader
        mat.InsertShader(nrm_shader)

        # Dispacement
        if self.GetBool(id=self.ADVANCED_SETTINGS+2) and ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4))):
            mat[c4d.MATERIAL_USE_DISPLACEMENT] = True
            mat[c4d.MATERIAL_DISPLACEMENT_SUBPOLY] = True
            mat[c4d.MATERIAL_DISPLACEMENT_HEIGHT] = 0.5*multiplier
            if self.GetBool(id=self.ADVANCED_SETTINGS+4) == True and "DISP16_" in matInfo:
                DispMap = self.Create_Bitmap(mat, matInfo, "DISP16_", "DISPLACEMENT", c4d.MATERIAL_DISPLACEMENT_SHADER, False)
            else:
                DispMap = self.Create_Bitmap(mat, matInfo, "DISP_", "DISPLACEMENT", c4d.MATERIAL_DISPLACEMENT_SHADER, False)
            DispMap[c4d.BITMAPSHADER_COLORPROFILE] = 1
            mat[c4d.MATERIAL_DISPLACEMENT_SUBPOLY] = True
            mat[c4d.MATERIAL_DISPLACEMENT_SUBPOLY_ROUND] = True

        # AlphaMasked
        if "ALPHAMASKED_" in matInfo:
            mat[c4d.MATERIAL_USE_ALPHA] = True
            self.Create_Bitmap(mat, matInfo, "ALPHAMASKED_", "ALPHAMASKED", c4d.MATERIAL_ALPHA_SHADER, False)


        mat.SetName(pName)
        return mat


    # ------------------------- #
    #       Octane Shader       #
    # ------------------------- #
    
    def CreateOctaneMat(self, matInfo, workflow):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        multiplier = self.getProjectScale()
        #doc = c4d.documents.GetActiveDocument()
        #for workflow in mapDict:
            #for res in mapDict[workflow]:
              #  for matn in mapDict[workflow][res]:
        
        doc = c4d.documents.GetActiveDocument()
        
        # Create material
        try:
            mat = c4d.BaseMaterial(1029501)
        except:
            return False
        
        try:
            mat[c4d.OCT_MATERIAL_TYPE] = 2516
            self.CreateOctaneUniversalMat(mat, matInfo, workflow)
            return mat
        except :
            pass
        
        try:
            mat[c4d.OCT_MATERIAL_TYPE] = 2511
        except:
            C4DVersionTwo = int(str(c4d.GetC4DVersion())[:2])
            VersionToUpdateTo = "R17.053"
            if C4DVersionTwo == 19: "R18.057"
            elif C4DVersionTwo == 19: "R19.053"
            elif C4DVersionTwo == 20: "R20.057"
            c4d.gui.MessageDialog("ERROR: Failed to create the octane material.\nPlease update your Cinema 4D to %s or later.", type=c4d.GEMB_ICONEXCLAMATION)
            return False
        
        # Set BRDF model to GGX, this wasn't avaliable in earlier Octane versions
        try:
            mat[c4d.OCT_MAT_BRDF_MODEL] = 2
        except:
            pass
        
        # COLOR
        COL_shader = c4d.BaseList2D(1029508)
        if "ALPHAMASKED_" in matInfo :
            if "MASK_" in matInfo and "SSS_" in matInfo :
                try : COL_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["COL_"]).encode('utf-8')
                except : COL_shader[c4d.IMAGETEXTURE_FILE] = matInfo["COL_"]
            else :
                try : COL_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["ALPHAMASKED_"]).encode('utf-8')
                except : COL_shader[c4d.IMAGETEXTURE_FILE] = matInfo["ALPHAMASKED_"]
        elif "COL_" in matInfo :
            try : COL_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["COL_"]).encode('utf-8')
            except : COL_shader[c4d.IMAGETEXTURE_FILE] = matInfo["COL_"]
        COL_shader.SetName("COLOR")
        mat.InsertShader(COL_shader)
        
        # Transmission
        if "TRANSMISSION_" in matInfo:
            Specmat = c4d.BaseMaterial(1029501)
            Specmat.SetName("%s_SPECULAR" %matInfo["Name"])
            Specmat[c4d.OCT_MATERIAL_TYPE] = 2513
            try:
                Specmat[c4d.OCT_MAT_BRDF_MODEL] = 2
            except:
                pass
        
        # AO
        if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) == True and "TRANSMISSION_" not in matInfo:
            blend_shader = c4d.BaseList2D(1029516)
            blend_shader.SetName("AO + COLOR (Multiply)")
            AO_shader = c4d.BaseList2D(1029508)
            AO_shader.SetName("AMBIENT OCCLUSION")
            try : AO_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["AO_"]).encode('utf-8')
            except : AO_shader[c4d.IMAGETEXTURE_FILE] = matInfo["AO_"]
            blend_shader[c4d.MULTIPLY_TEXTURE2] = AO_shader
            mat.InsertShader(blend_shader)
            mat.InsertShader(AO_shader)
            
            if workflow == "DIALECTRIC":
                blend_shader[c4d.MULTIPLY_TEXTURE1] = COL_shader
                mat[c4d.OCT_MATERIAL_DIFFUSE_LINK] = blend_shader
            else:
                mat[c4d.OCT_MATERIAL_DIFFUSE_LINK] = COL_shader
        else:
            # Don't use an AO map, only plug in the color
            mat[c4d.OCT_MATERIAL_DIFFUSE_LINK] = COL_shader
        
        # Reflection
        
        if "REFL_" in matInfo:
            if workflow == "DIALECTRIC":
                ReflMultiplyNode = c4d.BaseList2D(1029516)
                ReflMultiplyNode.SetName("REFLECTION")
                refl_shader = self.OCTANE_CreateShader(ReflMultiplyNode, matInfo, "REFL_", "REFLECTION", c4d.MULTIPLY_TEXTURE1, True)
                ReflColorMultiply = c4d.BaseList2D(5832)
                ReflColorMultiply.SetName("REFLECTION Adjust")
                ReflColorMultiply[c4d.COLORSHADER_BRIGHTNESS] = 0.6
                ReflMultiplyNode[c4d.MULTIPLY_TEXTURE2] = ReflColorMultiply
                mat.InsertShader(ReflColorMultiply)
                mat.InsertShader(ReflMultiplyNode)
                mat[c4d.OCT_MATERIAL_SPECULAR_LINK] = ReflMultiplyNode
                mat[c4d.OCT_MATERIAL_INDEX] = 1.6
            else:
                refl_shader = self.OCTANE_CreateShader(mat, matInfo, "REFL_", "REFLECTION", c4d.OCT_MATERIAL_SPECULAR_LINK, False)
                #refl_shader[c4d.IMAGETEXTURE_INVERT] = False
                mat[c4d.OCT_MATERIAL_INDEX] = 1
        
        # Gloss
        if "GLOSS_" in matInfo :
            GLOSS_shader = self.OCTANE_CreateShader(mat, matInfo, "GLOSS_", "GLOSS", c4d.OCT_MATERIAL_ROUGHNESS_LINK, True)
            GLOSS_shader[c4d.IMAGETEXTURE_GAMMA] = 1
        
        # Normals
        
        if self.GetBool(id=self.ADVANCED_SETTINGS+4) == True and "NRM16_" in matInfo:
            NRM_shader = self.OCTANE_CreateShader(mat, matInfo, "NRM16_", "NORMALS", c4d.OCT_MATERIAL_NORMAL_LINK, False)
            if "TRANSMISSION_" in matInfo:
                self.OCTANE_CreateShader(Specmat, matInfo, "NRM16_", "NORMALS", c4d.OCT_MATERIAL_NORMAL_LINK, False)
        elif "NRM_" in matInfo :
            NRM_shader = self.OCTANE_CreateShader(mat, matInfo, "NRM_", "NORMALS", c4d.OCT_MATERIAL_NORMAL_LINK, False)
            if "TRANSMISSION_" in matInfo:
                self.OCTANE_CreateShader(Specmat, matInfo, "NRM_", "NORMALS", c4d.OCT_MATERIAL_NORMAL_LINK, False)
        
        # Displacements
        
        # ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! #
        #                                                                                                                           #
        # There was an error reported were c4d.OCT_MATERIAL_DISPLACEMENT_LINK didn't exist. So it might have been moved in          #
        # Octane version 4. For now it's placed in a try catch, but this means displacements wont work in newer versions of Octane. #
        # This should be looked into ASAP to find out what c4d.OCT_MATERIAL_DISPLACEMENT_LINK is called now.                        #
        #                                                                                                                           #
        # ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! #
        
        if self.GetBool(id=self.ADVANCED_SETTINGS+2):
            try:
                if ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4))):
                    doc.InsertMaterial(mat)
                    doc.SetActiveMaterial(mat, c4d.SELECTION_NEW)
                    c4d.CallButton(mat, c4d.ID_MATERIAL_ADD_DISPLACEMENT)
                    if "TRANSMISSION_" in matInfo:
                        doc.InsertMaterial(Specmat)
                        doc.SetActiveMaterial(Specmat, c4d.SELECTION_NEW)
                        c4d.CallButton(Specmat, c4d.ID_MATERIAL_ADD_DISPLACEMENT)
                    if "DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4) == True:
                        try :
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP16_", "DISPLACEMENT", c4d.DISPLACEMENT_TEXTURE, False)
                            if "TRANSMISSION_" in matInfo:
                                DispMap = self.Create_Bitmap(Specmat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP16_", "DISPLACEMENT", c4d.DISPLACEMENT_TEXTURE, False)
                        except:
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP16_", "DISPLACEMENT", c4d.DISPLACEMENT_INPUT, False)
                            if "TRANSMISSION_" in matInfo:
                                DispMap = self.Create_Bitmap(Specmat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP16_", "DISPLACEMENT", c4d.DISPLACEMENT_INPUT, False)
                    else:
                        try :
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP_", "DISPLACEMENT", c4d.DISPLACEMENT_TEXTURE, False)
                            if "TRANSMISSION_" in matInfo:
                                self.Create_Bitmap(Specmat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP_", "DISPLACEMENT", c4d.DISPLACEMENT_TEXTURE, False)
                        except:
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP_", "DISPLACEMENT", c4d.DISPLACEMENT_INPUT, False)
                            if "TRANSMISSION_" in matInfo:
                                self.Create_Bitmap(Specmat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP_", "DISPLACEMENT", c4d.DISPLACEMENT_INPUT, False)
                    DispMap[c4d.BITMAPSHADER_COLORPROFILE] = 1
                    mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK][c4d.DISPLACEMENT_AMOUNT] = 0.5*multiplier
                    mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK][c4d.DISPLACEMENT_LEVELOFDETAIL] = 10
                    if "TRANSMISSION_" in matInfo:
                        Specmat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK][c4d.DISPLACEMENT_AMOUNT] = 0.5*multiplier
                        Specmat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK][c4d.DISPLACEMENT_LEVELOFDETAIL] = 10
            except: pass
        
        # Alphamasked
        
        if "ALPHAMASKED_" in matInfo:
            AO_shader = self.OCTANE_CreateShader(mat, matInfo, "ALPHAMASKED_", "ALPHAMASKED", c4d.OCT_MATERIAL_OPACITY_LINK, False)
            AO_shader[c4d.IMAGETEXTURE_MODE] = 2
        
        # Transmission
        
        if "TRANSMISSION_" in matInfo:
            # Create a Mix Material
            mat.SetName("%s_GLOSSY" %matInfo["Name"])
            GLOSS_shader_S = self.OCTANE_CreateShader(Specmat, matInfo, "GLOSS_", "GLOSS", c4d.OCT_MATERIAL_ROUGHNESS_LINK, True)
            GLOSS_shader_S[c4d.IMAGETEXTURE_GAMMA] = 1
            try:
                self.OCTANE_CreateShader(Specmat, matInfo, "REFL_", "REFLECTION", c4d.OCT_MATERIAL_REFLECTION_LINK, True)
            except:
                try:
                    self.OCTANE_CreateShader(Specmat, matInfo, "REFL_", "REFLECTION", c4d.OCT_MAT_REFLECTION_LINK, True)
                except:
                    pass
            self.OCTANE_CreateShader(Specmat, matInfo, "COL_", "COLOR", c4d.OCT_MATERIAL_TRANSMISSION_LINK, False)
            Specmat[c4d.OCT_MATERIAL_FAKESHADOW] = True
            GLOSS_shader[c4d.IMAGETEXTURE_GAMMA] = 1

            Mixmat = c4d.BaseMaterial(1029622)
            Mixmat.SetName(matInfo["Name"])
            Mixmat[c4d.MIXMATERIAL_TEXTURE1] = Specmat
            Mixmat[c4d.MIXMATERIAL_TEXTURE2] = mat
            c4d.CallButton(Mixmat, c4d.MIXMATERIAL_AMOUNT_BTN)
            self.OCTANE_CreateShader(Mixmat, matInfo, "TRANSMISSION_", "TRANSMISSION", c4d.MIXMATERIAL_AMOUNT_LNK, False)

            doc.InsertMaterial(Specmat)
            doc.InsertMaterial(Mixmat)
        
        # SSS
        
        if "SSS_" in matInfo:
            mat.SetName("%s_GLOSSY" %matInfo["Name"])
            
            Specmat = c4d.BaseMaterial(1029501)
            Specmat.SetName("%s_SPECULAR" %matInfo["Name"])
            Specmat[c4d.OCT_MATERIAL_TYPE] = 2513
            Specmat[c4d.OCT_MATERIAL_ROUGHNESS_FLOAT] = 1
            Specmat[c4d.OCT_MATERIAL_INDEX] = 1
            doc.InsertMaterial(Specmat)
            doc.SetActiveMaterial(Specmat, c4d.SELECTION_NEW)
            c4d.CallButton(Specmat, c4d.ID_MATERIAL_ADD_SCT_MEDIUM)
            ScatteringMedium = Specmat[c4d.OCT_MATERIAL_MEDIUM]
            ScatteringMedium[c4d.SCATTERINGMEDIUM_DENSITY] = 70
            self.OCTANE_CreateShader(Specmat, matInfo, "SSS_", "Subsurface Scattering", c4d.OCT_MATERIAL_TRANSMISSION_LINK, False)
            
            Mixmat = c4d.BaseMaterial(1029622)
            Mixmat.SetName(matInfo["Name"])
            Mixmat[c4d.MIXMATERIAL_TEXTURE1] = Specmat
            Mixmat[c4d.MIXMATERIAL_TEXTURE2] = mat
            Mixmat[c4d.MIXMATERIAL_AMOUNT_FLOAT] = 0.2
            if 'Plant' in matInfo["Name"] : Mixmat[c4d.MIXMATERIAL_AMOUNT_FLOAT] = 0.5
            
            pSSS = self.OCTANE_CreateShader(Specmat, matInfo, "SSS_", "Subsurface Scattering 1", c4d.MIXMATERIAL_AMOUNT_LNK, False)
            pSSS[c4d.IMAGETEXTURE_GAMMA] = 1.0
            c4d.CallButton(Mixmat, c4d.MIXMATERIAL_AMOUNT_BTN)
            Mixmat[c4d.MIXMATERIAL_AMOUNT_LNK] = pSSS
            
            doc.InsertMaterial(Mixmat)
            
            if "ALPHAMASKED_" in matInfo and "MASK_" in matInfo :
                Specmat[c4d.OCT_MATERIAL_ROUGHNESS_FLOAT] = 0.1
        
        # Conform UV Maps
        # WIP, these are just experiments, this is not supported yet.
        if False: #self.GetBool(id=self.ADVANCED_SETTINGS+3):
            #c4d.CallButton(COL_shader, c4d.UVW_TRANS_TRANSFORM_BTN)
            COL_shader[c4d.UVW_TRANS_TRANSFORM_BTN] = True
            Transform = c4d.BaseShader(1030961)
            Transform[c4d.TRANSFORM_SCL_LOCK] = False
            Transform[c4d.TRANSFORM_SX] = 3.14
            Transform[c4d.TRANSFORM_SY] = 3.14
            COL_shader[c4d.IMAGETEXTURE_TRANSFORM_LINK] = Transform
        
        # Update the material and add it to the current document
        #mat.Update(True, True)
        #doc.InsertMaterial(mat)
        
        # Import a model (internal only)
        if internal:
            if "TRANSMISSION_" in matInfo or "SSS_" in matInfo:
                return Mixmat
                #self.ImportModel(Mixmat, matn)
            else:
                return mat
                #self.ImportModel(mat, matn)
        
        mat.SetName(pName)
        return mat
    
    def CreateOctaneUniversalMat(self, mat, matInfo, workflow):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        multiplier = self.getProjectScale()
        
        doc = c4d.documents.GetActiveDocument()
        
        # Set BRDF model to GGX, this wasn't avaliable in earlier Octane versions
        try:
            mat[c4d.OCT_MAT_BRDF_MODEL] = 2
        except:
            pass
        
        mat[c4d.OCT_MAT_SPECULAR_MAP_FLOAT] = 0.0
        
        print(json.dumps(matInfo,indent=1))
        
        # COLOR -----------------------------------------------------------------
        print ('COLOR')
        
        COL_shader = c4d.BaseList2D(1029508)
        if "ALPHAMASKED_" in matInfo :
            if "MASK_" in matInfo and "SSS_" in matInfo :
                try : COL_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["COL_"]).encode('utf-8')
                except : COL_shader[c4d.IMAGETEXTURE_FILE] = matInfo["COL_"]
            else :
                try : COL_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["ALPHAMASKED_"]).encode('utf-8')
                except : COL_shader[c4d.IMAGETEXTURE_FILE] = matInfo["ALPHAMASKED_"]
        elif "COL_" in matInfo :
            try : COL_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["COL_"]).encode('utf-8')
            except : COL_shader[c4d.IMAGETEXTURE_FILE] = matInfo["COL_"]
        COL_shader.SetName("COLOR")
        COL_shader[c4d.IMAGETEXTURE_MODE] = 0
        mat.InsertShader(COL_shader)
        
        # AO -----------------------------------------------------------------
        print ('AO')
        
        if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) == True:
            blend_shader = c4d.BaseList2D(1029516)
            blend_shader.SetName("AO + COLOR (Multiply)")
            AO_shader = c4d.BaseList2D(1029508)
            AO_shader.SetName("AMBIENT OCCLUSION")
            AO_shader[c4d.IMAGETEXTURE_MODE] = 0
            try : AO_shader[c4d.IMAGETEXTURE_FILE] = (matInfo["AO_"]).encode('utf-8')
            except : AO_shader[c4d.IMAGETEXTURE_FILE] = matInfo["AO_"]
            blend_shader[c4d.MULTIPLY_TEXTURE2] = AO_shader
            mat.InsertShader(blend_shader)
            mat.InsertShader(AO_shader)
            
            if workflow == "DIALECTRIC":
                blend_shader[c4d.MULTIPLY_TEXTURE1] = COL_shader
                mat[c4d.OCT_MATERIAL_DIFFUSE_LINK] = blend_shader
            else:
                mat[c4d.OCT_MATERIAL_DIFFUSE_LINK] = COL_shader
        else:
            # Don't use an AO map, only plug in the color
            mat[c4d.OCT_MATERIAL_DIFFUSE_LINK] = COL_shader
        
        if 'METALNESS_' in matInfo:
            # Metalness -----------------------------------------------------------------
            print ('Metalness')
            
            METAL_shader = self.OCTANE_CreateShader(mat, matInfo, "METALNESS_", "METALNESS", c4d.OCT_MAT_SPECULAR_MAP_LINK, False)
            METAL_shader[c4d.IMAGETEXTURE_MODE] = 1
            #METAL_shader[c4d.IMAGETEXTURE_GAMMA] = 1
            
            # Roughness -----------------------------------------------------------------
            print ('Roughness')
            
            if "ROUGHNESS_" in matInfo :
                ROUGHNESS_shader = self.OCTANE_CreateShader(mat, matInfo, "ROUGHNESS_", "ROUGHNESS", c4d.OCT_MATERIAL_ROUGHNESS_LINK, False)
                ROUGHNESS_shader[c4d.IMAGETEXTURE_MODE] = 1
                #ROUGHNESS_shader[c4d.IMAGETEXTURE_GAMMA] = 1
            
        else :
            # Reflection -----------------------------------------------------------------
            print ('Reflection')
            
            if "REFL_" in matInfo:
                if workflow == "DIALECTRIC":
                    ReflMultiplyNode = c4d.BaseList2D(1029516)
                    ReflMultiplyNode.SetName("REFLECTION")
                    refl_shader = self.OCTANE_CreateShader(ReflMultiplyNode, matInfo, "REFL_", "REFLECTION", c4d.MULTIPLY_TEXTURE1, True)
                    refl_shader[c4d.IMAGETEXTURE_MODE] = 0
                    ReflColorMultiply = c4d.BaseList2D(5832)
                    ReflColorMultiply.SetName("REFLECTION Adjust")
                    ReflColorMultiply[c4d.COLORSHADER_BRIGHTNESS] = 0.6
                    ReflMultiplyNode[c4d.MULTIPLY_TEXTURE2] = ReflColorMultiply
                    mat.InsertShader(ReflColorMultiply)
                    mat.InsertShader(ReflMultiplyNode)
                    mat[c4d.OCT_MATERIAL_SPECULAR_LINK] = ReflMultiplyNode
                    mat[c4d.OCT_MATERIAL_INDEX] = 1.6
                else:
                    refl_shader = self.OCTANE_CreateShader(mat, matInfo, "REFL_", "REFLECTION", c4d.OCT_MATERIAL_SPECULAR_LINK, False)
                    #refl_shader[c4d.IMAGETEXTURE_INVERT] = False
                    mat[c4d.OCT_MATERIAL_INDEX] = 1
            
            # Gloss -----------------------------------------------------------------
            print ('Gloss')
            
            if "GLOSS_" in matInfo :
                GLOSS_shader = self.OCTANE_CreateShader(mat, matInfo, "GLOSS_", "GLOSS", c4d.OCT_MATERIAL_ROUGHNESS_LINK, True)
                GLOSS_shader[c4d.IMAGETEXTURE_MODE] = 1
                GLOSS_shader[c4d.IMAGETEXTURE_GAMMA] = 1
        
        # Normals -----------------------------------------------------------------
        print ('Normals')
        
        if self.GetBool(id=self.ADVANCED_SETTINGS+4) == True and "NRM16_" in matInfo:
            NRM_shader = self.OCTANE_CreateShader(mat, matInfo, "NRM16_", "NORMALS", c4d.OCT_MATERIAL_NORMAL_LINK, False)
        elif "NRM_" in matInfo :
            NRM_shader = self.OCTANE_CreateShader(mat, matInfo, "NRM_", "NORMALS", c4d.OCT_MATERIAL_NORMAL_LINK, False)
        
        # Displacements -----------------------------------------------------------------
        print ('Displacements')
        
        # ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! #
        #                                                                                                                           #
        # There was an error reported were c4d.OCT_MATERIAL_DISPLACEMENT_LINK didn't exist. So it might have been moved in          #
        # Octane version 4. For now it's placed in a try catch, but this means displacements wont work in newer versions of Octane. #
        # This should be looked into ASAP to find out what c4d.OCT_MATERIAL_DISPLACEMENT_LINK is called now.                        #
        #                                                                                                                           #
        # ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! #
        
        if self.GetBool(id=self.ADVANCED_SETTINGS+2):
            try:
                if ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4))):
                    doc.InsertMaterial(mat)
                    doc.SetActiveMaterial(mat, c4d.SELECTION_NEW)
                    c4d.CallButton(mat, c4d.ID_MATERIAL_ADD_DISPLACEMENT)
                    if "DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4) == True:
                        try :
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP16_", "DISPLACEMENT", c4d.DISPLACEMENT_TEXTURE, False)
                        except:
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP16_", "DISPLACEMENT", c4d.DISPLACEMENT_INPUT, False)
                    else:
                        try :
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP_", "DISPLACEMENT", c4d.DISPLACEMENT_TEXTURE, False)
                        except:
                            DispMap = self.Create_Bitmap(mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK], matInfo, "DISP_", "DISPLACEMENT", c4d.DISPLACEMENT_INPUT, False)
                    DispMap[c4d.BITMAPSHADER_COLORPROFILE] = 1
                    mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK][c4d.DISPLACEMENT_AMOUNT] = 0.5*multiplier
                    mat[c4d.OCT_MATERIAL_DISPLACEMENT_LINK][c4d.DISPLACEMENT_LEVELOFDETAIL] = 10
            except: pass
        
        # Alphamasked -----------------------------------------------------------------
        print ('Alphamasked')
        
        if "ALPHAMASKED_" in matInfo:
            AO_shader = self.OCTANE_CreateShader(mat, matInfo, "ALPHAMASKED_", "ALPHAMASKED", c4d.OCT_MATERIAL_OPACITY_LINK, False)
            AO_shader[c4d.IMAGETEXTURE_MODE] = 2
        
        # SSS -----------------------------------------------------------------
        print ('SSS')
        
        if "SSS_" in matInfo:
            mat.SetName("%s_GLOSSY" %matInfo["Name"])
            
            pSSS = self.OCTANE_CreateShader(mat, matInfo, "SSS_", "Subsurface Scattering", c4d.OCT_MATERIAL_TRANSMISSION_LINK, False)
            pSSS[c4d.IMAGETEXTURE_MODE] = 0
            #pSSS[c4d.IMAGETEXTURE_GAMMA] = 1.0
            
            c4d.CallButton(mat, c4d.ID_MATERIAL_ADD_SCT_MEDIUM)
            Scatter = mat[c4d.OCT_MATERIAL_MEDIUM]
            Scatter[c4d.SCATTERINGMEDIUM_ABSORPTION] = pSSS
            Scatter[c4d.SCATTERINGMEDIUM_SCATTERING] = pSSS
        
        # Conform UV Maps
        # WIP, these are just experiments, this is not supported yet.
        if False: #self.GetBool(id=self.ADVANCED_SETTINGS+3):
            #c4d.CallButton(COL_shader, c4d.UVW_TRANS_TRANSFORM_BTN)
            COL_shader[c4d.UVW_TRANS_TRANSFORM_BTN] = True
            Transform = c4d.BaseShader(1030961)
            Transform[c4d.TRANSFORM_SCL_LOCK] = False
            Transform[c4d.TRANSFORM_SX] = 3.14
            Transform[c4d.TRANSFORM_SY] = 3.14
            COL_shader[c4d.IMAGETEXTURE_TRANSFORM_LINK] = Transform
        
        mat.SetName(pName)
        return mat
    
    # Create the octane texture
    def OCTANE_CreateShader(self, mat, matInfo, MAP, NAME, LINK, INV):
        shader = c4d.BaseList2D(1029508)
        try : shader[c4d.IMAGETEXTURE_FILE] = (matInfo[MAP]).encode('utf-8')
        except : shader[c4d.IMAGETEXTURE_FILE] = matInfo[MAP]
        shader[c4d.IMAGETEXTURE_INVERT] = INV
        shader.SetName(NAME)
        mat[LINK] = shader
        mat.InsertShader(shader)
        return shader
    
    # ------------------------- #
    #       Corona Shader       #
    # ------------------------- #

    def CreateCoronaMat(self, matInfo, workflow):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        multiplier = self.getProjectScale()
        doc = c4d.documents.GetActiveDocument()
        #for workflow in mapDict:
        #    for res in mapDict[workflow]:
        #        for matn in mapDict[workflow][res]:


        doc = c4d.documents.GetActiveDocument()

        # Create the material
        try:
            mat = c4d.BaseMaterial(1032100)
        except:
            return False
        
        # COLOR & AO ------------------------------------------------------------------------------------------------------------------------
        
        if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) and workflow == "DIALECTRIC":
            Fusion_shader = c4d.BaseList2D(c4d.Xfusion)
            Fusion_shader.SetName("COLOR + AO")
            if "ALPHAMASKED_" in matInfo :
                if "MASK_" in matInfo and "SSS_" in matInfo :
                    self.Create_Bitmap(Fusion_shader, matInfo, "COL_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
                else :
                    self.Create_Bitmap(Fusion_shader, matInfo, "ALPHAMASKED_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
            else :
                self.Create_Bitmap(Fusion_shader, matInfo, "COL_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
            self.Create_Bitmap(Fusion_shader, matInfo, "AO_", "AMBIENT OCCLUSION", c4d.SLA_FUSION_BLEND_CHANNEL, False)
            Fusion_shader[c4d.SLA_FUSION_MODE] = 2019
            mat[c4d.MATERIAL_COLOR_TEXTUREMIXING] = 3 # Might not be supported in a CORONA material ?
            mat[c4d.CORONA_DIFFUSE_TEXTURE] = Fusion_shader
            mat.InsertShader(Fusion_shader)
        else:
            if "ALPHAMASKED_" in matInfo :
                if "MASK_" in matInfo and "SSS_" in matInfo :
                    self.Create_Bitmap(mat, matInfo, "COL_", "COLOR", c4d.CORONA_DIFFUSE_TEXTURE, False)
                else :
                    pAlpha = self.Create_Bitmap(mat, matInfo, "ALPHAMASKED_", "COLOR", c4d.CORONA_DIFFUSE_TEXTURE, False)
            else :
                self.Create_Bitmap(mat, matInfo, "COL_", "COLOR", c4d.CORONA_DIFFUSE_TEXTURE, False)


        # Reflection ------------------------------------------------------------------------------------------------------------------------
        
        if "REFL_" in matInfo:
            mat[c4d.CORONA_MATERIAL_REFLECT] = True
            if workflow == "DIALECTRIC":
                REFL_Shader = self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", c4d.CORONA_REFLECT_TEXTURE, True)
                mat[c4d.CORONA_REFLECT_FRESNELLOR_VALUE] = 1.7
                REFL_Shader[c4d.BITMAPSHADER_BLACKPOINT] = 0.6
            else:
                REFL_Shader = self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", c4d.CORONA_REFLECT_TEXTURE, False)
                mat[c4d.CORONA_REFLECT_FRESNELLOR_VALUE] = 100

        #GLOSS ------------------------------------------------------------------------------------------------------------------------
        
        if "GLOSS_" in matInfo :
            GLOSS_Shader = self.Create_Bitmap(mat, matInfo, "GLOSS_", "GLOSS", c4d.CORONA_REFLECT_GLOSSINESS_TEXTURE, False)
            GLOSS_Shader[c4d.BITMAPSHADER_COLORPROFILE] = 1

        #NRM ------------------------------------------------------------------------------------------------------------------------
        
        NRM_shader = c4d.BaseList2D(1035405)
        mat[c4d.CORONA_BUMPMAPPING_TEXTURE] = NRM_shader
        mat.InsertShader(NRM_shader)
        mat[c4d.CORONA_MATERIAL_BUMPMAPPING] = True
        mat[c4d.CORONA_BUMPMAPPING_STRENGTH] = 1
        NRM_shader[c4d.CORONA_NORMALMAP_FLIP_G] = True
        #mat[c4d.CORONA_BUMPMAPPING_TEXTURE] = c4d.CORONA_MATERIAL_BUMPMAPPING

        if "NRM16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
            self.Create_Bitmap(mat[c4d.CORONA_BUMPMAPPING_TEXTURE], matInfo, "NRM16_", "NORMAL", c4d.CORONA_NORMALMAP_TEXTURE, False)
        elif "NRM_" in matInfo :
            self.Create_Bitmap(mat[c4d.CORONA_BUMPMAPPING_TEXTURE], matInfo, "NRM_", "NORMAL", c4d.CORONA_NORMALMAP_TEXTURE, False)

        # Displacement ------------------------------------------------------------------------------------------------------------------------
        
        if self.GetBool(id=self.ADVANCED_SETTINGS+2) and ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4))):
            mat[c4d.CORONA_MATERIAL_DISPLACEMENT] = True
            mat[c4d.CORONA_DISPLACEMENT_MAX_LEVEL] = 0.5*multiplier
            if "DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4) == True:
                DispMap = self.Create_Bitmap(mat, matInfo, "DISP16_", "DISPLACEMENT", c4d.CORONA_DISPLACEMENT_TEXTURE, False)
            else:
                DispMap = self.Create_Bitmap(mat, matInfo, "DISP_", "DISPLACEMENT", c4d.CORONA_DISPLACEMENT_TEXTURE, False)
            DispMap[c4d.BITMAPSHADER_COLORPROFILE] = 1

        # Alphamasked ------------------------------------------------------------------------------------------------------------------------
        
        if "MASK_" in matInfo:
            mat[c4d.CORONA_MATERIAL_ALPHA] = True
            Alpha_shader = c4d.BaseList2D(1036473)
            try : Alpha_shader[c4d.CORONA_BITMAP_FILENAME] = (matInfo["MASK_"]).encode('utf-8')
            except : Alpha_shader[c4d.CORONA_BITMAP_FILENAME] = matInfo["MASK_"]
            Alpha_shader[c4d.CORONA_BITMAP_CHANNELS_ALPHA] = 1
            Alpha_shader[c4d.CORONA_BITMAP_CHANNELS_MONO] = 1
            Alpha_shader[c4d.CORONA_BITMAP_CHANNELS_RGB] = 1
            Alpha_shader.SetName("MASK")
            mat[c4d.CORONA_ALPHA_TEXTURE] = Alpha_shader
            mat.InsertShader(Alpha_shader)

        elif "ALPHAMASKED_" in matInfo:
            mat[c4d.CORONA_MATERIAL_ALPHA] = True
            Alpha_shader = c4d.BaseList2D(1036473)
            try : Alpha_shader[c4d.CORONA_BITMAP_FILENAME] = (matInfo["ALPHAMASKED_"]).encode('utf-8')
            except : Alpha_shader[c4d.CORONA_BITMAP_FILENAME] = matInfo["ALPHAMASKED_"]
            Alpha_shader[c4d.CORONA_BITMAP_CHANNELS_ALPHA] = 1
            Alpha_shader[c4d.CORONA_BITMAP_CHANNELS_MONO] = 1
            Alpha_shader[c4d.CORONA_BITMAP_CHANNELS_RGB] = 1
            Alpha_shader.SetName("ALPHAMASKED")
            mat[c4d.CORONA_ALPHA_TEXTURE] = Alpha_shader
            mat.InsertShader(Alpha_shader)

        # Transmission ------------------------------------------------------------------------------------------------------------------------
        
        if "TRANSMISSION_" in matInfo:
            mat[c4d.CORONA_MATERIAL_REFRACT] = 1
            self.Create_Bitmap(mat, matInfo, "COL_", "COLOR", c4d.CORONA_REFRACT_TEXTURE, False)
            GLOSS_Shader = self.Create_Bitmap(mat, matInfo, "GLOSS_", "GLOSS", c4d.CORONA_REFRACT_GLOSSINESS_TEXTURE, False)
            GLOSS_Shader[c4d.BITMAPSHADER_COLORPROFILE] = 1

        # SSS ------------------------------------------------------------------------------------------------------------------------
        
        if "SSS_" in matInfo:
            mat[c4d.CORONA_MATERIAL_VOLUME] = True
            SSSMap = self.Create_Bitmap(mat, matInfo, "SSS_", "SSS", c4d.CORONA_VOLUME_SSS_TEXTURE, False)
            mat[c4d.CORONA_VOLUME_MODE] = 1
            mat[c4d.CORONA_VOLUME_SSS_FRACTION_VALUE] = 1
            mat[c4d.CORONA_VOLUME_SSS_RADIUS_VALUE] = 2*multiplier
            mat[c4d.CORONA_VOLUME_SSS_COLOR] = c4d.Vector(0.0, 0.0, 0.0)
            
            if "ALPHAMASKED_" in matInfo and "MASK_" in matInfo :
                mat[c4d.CORONA_VOLUME_MODE] = c4d.CORONA_VOLUME_MODE_VOLUMETRIC
                
                mat[c4d.CORONA_MATERIAL_TRANSLUCENCY] = True
                mat[c4d.CORONA_TRANSLUCENCY_LEVEL] = 100
                mat[c4d.CORONA_TRANSLUCENCY_LEVEL_TEXTURE] = SSSMap
                mat[c4d.CORONA_TRANSLUCENCY_TEXTURE] = SSSMap

        # Update and add the material into the current document
        mat.Update(True, True)
        doc.InsertMaterial(mat)

        mat.SetName(pName)
        return mat

    # Create a bitmap texture/shader
    def Create_Bitmap(self, mat, matInfo, MAP, NAME, LINK, INV):
        shader = c4d.BaseList2D(c4d.Xbitmap)
        if MAP in matInfo:
            try:
                shader[c4d.BITMAPSHADER_FILENAME] = (matInfo[MAP]).encode('utf-8')
            except:
                shader[c4d.BITMAPSHADER_FILENAME] = matInfo[MAP]
        if INV:
            shader[c4d.BITMAPSHADER_BLACKPOINT] = 1
            shader[c4d.BITMAPSHADER_WHITEPOINT] = 0
        shader.SetName(NAME)
        mat[LINK] = shader
        mat.InsertShader(shader)
        return shader



    # ------------------------- #
    #      Redshift Shader      #
    # ------------------------- #

    def CreateRedshiftMat(self, matInfo, workflow):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        # Import the redshift library
        try:
            import redshift
        except:
            print ("ERROR: Could not import the Redshift Python library.")
            return False

        #for workflow in mapDict:
            #for res in mapDict[workflow]:
                #for matn in mapDict[workflow][res]:


        doc = c4d.documents.GetActiveDocument()

        # Create the material
        c4d.CallCommand(1036759, 1000)
        mat = doc.GetFirstMaterial()

        NodeMaster = redshift.GetRSMaterialNodeMaster(mat)
        if NodeMaster == None :
            try :
                c4d.CallCommand(300001024)
                c4d.CallCommand(1040228)
                c4d.CallCommand(1036759, 1000)
                mat = doc.GetFirstMaterial()
                NodeMaster = redshift.GetRSMaterialNodeMaster(mat)
                c4d.CallCommand(1040228)
            except : pass

        if NodeMaster == None :
            print ("ERROR: NodeMaster not found.")
            return False
        root = NodeMaster.GetRoot()

        output = root.GetDown()
        RShader = output.GetNext()

        # Add some outputs to the redshift node
        RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_DIFFUSE_COLOR)), message=True)
        RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_REFL_COLOR)), message=True)
        RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_REFL_ROUGHNESS)), message=True)
        RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(10062)), message=True)

        RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFL_BRDF] = 1

        nodeList = []
        p = 0 # Extra ports added to the RShader

        #node = Node(self._gvMaster.CreateNode(self._gvMaster.GetRoot(), 1036746, NodeBefore, x, y), self.doUndo)

        # COLOR & AO -----------------------------------------------------------------------------------------------------------------------------

        COL_NODE = None
        Layer_Node = None
        AO_NODE = None
        if "SSS_" not in matInfo and "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) == True and workflow == "DIALECTRIC":
            Layer_Node = NodeMaster.CreateNode(root, 1036227, None, -190, 150)
            Layer_Node[c4d.GV_REDSHIFT_SHADER_META_CLASSNAME] = "RSColorLayer"
            Layer_Node[c4d.ID_BASELIST_NAME] = "AO + COLOR MULTIPLY"
            Layer_Node[c4d.ID_GVBASE_COLOR] = c4d.Vector(0.788, 0.557, 0.537)
            for i in range(0,3):
                Layer_Node.RemovePort(Layer_Node.GetInPort(2))
            if "ALPHAMASKED_" in matInfo :
                if "MASK_" in matInfo and "SSS_" in matInfo :
                    COL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "COL_", "COLOR", 0, Layer_Node, False, -350, 150)
                else :
                    COL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "ALPHAMASKED_", "COLOR", 0, Layer_Node, False, -350, 150)
            else :
                COL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "COL_", "COLOR", 0, Layer_Node, False, -350, 150)
            AO_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "AO_", "AO", 1, Layer_Node, False, -350, 200)
            nodeList.append(AO_NODE)
            Layer_Node[c4d.REDSHIFT_SHADER_RSCOLORLAYER_LAYER1_BLEND_MODE] = 4
            if not self.GetBool(id=self.CHECKBOX_IS_METAL) or "REFL_" not in matInfo:
                Layer_Node.GetOutPort(0).Connect(RShader.GetInPort(0))
        else:
            if "ALPHAMASKED_" in matInfo :
                if "MASK_" in matInfo and "SSS_" in matInfo :
                    COL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "COL_", "COLOR", 0, RShader, False, -50, 200)
                else :
                    COL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "ALPHAMASKED_", "COLOR", 0, RShader, False, -50, 200)
            else :
                COL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "COL_", "COLOR", 0, RShader, False, -50, 200)
            if not self.GetBool(id=self.CHECKBOX_IS_METAL) or "REFL_" not in matInfo:
                COL_NODE.GetOutPort(0).Connect(RShader.GetInPort(0))

        # Gloss -----------------------------------------------------------------------------------------------------------------------------
        GLOSS_NODE = None
        INV_GLOSS_NODE = None
        REFL_Multi_Node = None
        if "GLOSS_" in matInfo :
            GLOSS_NODE, INV_GLOSS_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "GLOSS_", "GLOSS", 2, RShader, True, -350, 300)

        # Reflection -----------------------------------------------------------------------------------------------------------------------------

        REFL_NODE = None
        INV_REFL_NODE = None
        if "REFL_" in matInfo:
            if workflow == "DIALECTRIC":
                res = self.CreateRedshiftNode(
                    NodeMaster, root, mat, matInfo, "REFL_", "REFLECTION", 1, RShader, False, -350, 250)
                if isinstance(res, tuple):
                    # Function above only unpacks to multi values in some scenarios.
                    REFL_NODE, INV_REFL_NODE = res
                else:
                    REFL_NODE = res
                if self.GetBool(id=self.CHECKBOX_IS_METAL):
                    REFL_NODE.GetOutPort(0).Connect(RShader.GetInPort(0))
                    COL_NODE.Remove()
                    if Layer_Node is not None:
                        Layer_Node.Remove()
                    if AO_NODE is not None:
                        AO_NODE.Remove()

            else:
                REFL_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "REFL_", "REFLECTION", 1, RShader, False, -350, 250)
                RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFL_IOR] = 0
                if self.GetBool(id=self.CHECKBOX_IS_METAL):
                    REFL_NODE.GetOutPort(0).Connect(RShader.GetInPort(0))
                    COL_NODE.Remove()
                    if Layer_Node is not None:
                        Layer_Node.Remove()
                    if AO_NODE is not None:
                        AO_NODE.Remove()

        if self.GetBool(id=self.CHECKBOX_IS_METAL):
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFL_FRESNEL_MODE] = 2  # Metallic
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFL_METALNESS] = 1.0

        # Normal -----------------------------------------------------------------------------------------------------------------------------

        # Check if normal map should be 16Bit
        if "NRM16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
            NrmType = "NRM16_"
        elif "NRM_" in matInfo:
            NrmType = "NRM_"

        # A user reported an error where BUMPMAP input type didn't exist
        UseBumpNode = True
        try:
            c4d.REDSHIFT_SHADER_BUMPMAP_INPUTTYPE
        except:
            UseBumpNode = False

        BUMP_NODE = None
        NRM_NODE = None
        if UseBumpNode:
            BUMP_NODE = NodeMaster.CreateNode(root, 1036227, None, -150, 350)
            BUMP_NODE[c4d.GV_REDSHIFT_SHADER_META_CLASSNAME] = 'BumpMap'
            BUMP_NODE[c4d.ID_BASELIST_NAME] = "RS BUMP NODE"
            BUMP_NODE[c4d.REDSHIFT_SHADER_BUMPMAP_INPUTTYPE] = 1
            BUMP_NODE[c4d.ID_GVBASE_COLOR] = c4d.Vector(0.345, 0.31, 0.459)
            BUMP_NODE.GetOutPort(0).Connect(RShader.GetInPort(3))
            BUMP_NODE.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(10000)), message=True)
            NRM_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, NrmType, "NORMALS", 0, BUMP_NODE, False, -350, 350)
        else:
            # Legacy version of loading in normals
            NRM_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, NrmType, "NORMALS", 3, RShader, False, -250, 350)

        # Displacement -----------------------------------------------------------------------------------------------------------------------------

        DISP_Node = None
        if self.GetBool(id=self.ADVANCED_SETTINGS+2) and ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4))):
            output.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(10001)), message=True)
            DISP_Node = NodeMaster.CreateNode(root, 1036227, None, 100, 450)
            DISP_Node[c4d.GV_REDSHIFT_SHADER_META_CLASSNAME] = "Displacement"
            DISP_Node[c4d.ID_GVBASE_COLOR] = c4d.Vector(0.345, 0.31, 0.459)
            DISP_Node.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(10000)), message=True)
            DISP_Node[c4d.REDSHIFT_SHADER_DISPLACEMENT_SCALE] = 0.5
            DISP_Node[c4d.REDSHIFT_SHADER_DISPLACEMENT_NEWRANGE_MIN] = -0.5
            DISP_Node[c4d.REDSHIFT_SHADER_DISPLACEMENT_NEWRANGE_MAX] = 0.5
            if "DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
                DISPNODETEX = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "DISP16_", "DISPLACEMENT", 0, DISP_Node, False, -80, 450)
            else:
                DISPNODETEX = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "DISP_", "DISPLACEMENT", 0, DISP_Node, False, -80, 450)

            nodeList.append(DISPNODETEX)
            DISP_Node.GetOutPort(0).Connect(output.GetInPort(1))

        # Mask/Alphamasked -----------------------------------------------------------------------------------------------------------------------------

        MASK_NODE = None
        Alpha_Node = None
        if "MASK_" in matInfo and "SSS_" in matInfo:
            p = 1
            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_OPACITY_COLOR)), message=True)
            MASK_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "MASK_", "MASK", 4, RShader, False, -250, 450)

        elif "ALPHAMASKED_" in matInfo:
            p = 1
            Alpha_Node = NodeMaster.CreateNode(root, 1036227, None, 100, 200)
            Alpha_Node[c4d.GV_REDSHIFT_SHADER_META_CLASSNAME] = "RSColorSplitter"
            if "SSS_" not in matInfo and "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) == True and workflow == "DIALECTRIC":
                Layer_Node.GetOutPort(0).Connect(Alpha_Node.GetInPort(0))
            else:
                COL_NODE.GetOutPort(0).Connect(Alpha_Node.GetInPort(0))
            Alpha_Node.AddPort(c4d.GV_PORT_OUTPUT, c4d.DescID(c4d.DescLevel(50001)), message=True)
            Alpha_Node.AddPort(c4d.GV_PORT_OUTPUT, c4d.DescID(c4d.DescLevel(50002)), message=True)
            Alpha_Node.AddPort(c4d.GV_PORT_OUTPUT, c4d.DescID(c4d.DescLevel(50003)), message=True)

            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_OPACITY_COLOR)), message=True)
            Alpha_Node.GetOutPort(3).Connect(RShader.GetInPort(4))

        # Transmission -----------------------------------------------------------------------------------------------------------------------------

        TRANSMISSION_NODE = None
        if "TRANSMISSION_" in matInfo:
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFR_USE_BASE_IOR] = False
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFR_WEIGHT] = 1
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_REFR_ABSORPTION_SCALE] = 1
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_ENERGYCOMPMODE] = 0
            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_REFR_COLOR)), message=True)
            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_REFR_ROUGHNESS)), message=True)
            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_REFR_WEIGHT)), message=True)
            TRANSMISSION_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "TRANSMISSION_", "TRANSMISSION", 6+p, RShader, False, -250, 400)
            if INV_GLOSS_NODE is not None:
                INV_GLOSS_NODE.GetOutPort(0).Connect(RShader.GetInPort(5+p))
            COL_NODE.GetOutPort(0).Connect(RShader.GetInPort(4+p))
            p+=3

        # SSS -----------------------------------------------------------------------------------------------------------------------------

        SSS_NODE = None
        SSS_NODE1 = None
        if "SSS_" in matInfo:
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_MS_AMOUNT] = 0.4
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_MS_RADIUS_SCALE] = 0.3
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_MS_WEIGHT0] = 1
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_MS_RADIUS_SCALE] = 2
            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_MS_COLOR0)), message=True)
            SSS_NODE = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "SSS_", "SSS", 4+p, RShader, False, -250, 500)

            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_TRANSL_COLOR)), message=True)
            SSS_NODE.GetOutPort(0).Connect(RShader.GetInPort(5+p))
            RShader[c4d.REDSHIFT_SHADER_MATERIAL_TRANSL_WEIGHT] = 1

            RShader.AddPort(c4d.GV_PORT_INPUT, c4d.DescID(c4d.DescLevel(c4d.REDSHIFT_SHADER_MATERIAL_MS_AMOUNT)), message=True)
            SSS_NODE1 = self.CreateRedshiftNode(NodeMaster, root, mat, matInfo, "SSS_", "SSS1", 6+p, RShader, False, -250, 550)

            p+=2

        # Conform UV Maps
        if self.GetBool(id=self.ADVANCED_SETTINGS+3):
            u, v = self.ConformUVMap(matInfo["COL_"])
            nodeList += [COL_NODE, REFL_NODE, NRM_NODE]
            if GLOSS_NODE is not None:
                nodeList +=  [GLOSS_NODE]
            for node in nodeList:
                if node is None:
                    continue  # Safeguard created in event REFL_NODE not defined.
                node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_SCALE] = c4d.Vector(u, v, 0)
            #NRM_NODE[c4d.REDSHIFT_SHADER_NORMALMAP_MAX_UV] = c4d.Vector(u, v, 0)

        mat.SetName(pName)
        return mat

    # Create a redshift texture node
    def CreateRedshiftNode(self, NodeMaster, root, mat, matInfo, MAP, NAME, LINK, RShader, INV, posX, posY):
        Node = NodeMaster.CreateNode(root, 1036227, None, posX, posY)
        #if NAME == "NORMALS": META_CLASSNAME = "NormalMap"
        #else: META_CLASSNAME = "TextureSampler"
        META_CLASSNAME = "TextureSampler"
        Node[c4d.GV_REDSHIFT_SHADER_META_CLASSNAME] = META_CLASSNAME
        Node[c4d.ID_BASELIST_NAME] = NAME
        Node[c4d.ID_GVBASE_COLOR] = c4d.Vector(0.663, 0.624, 0.424)
        try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_GAMMAOVERRIDE] = 1
        except : pass

        if MAP in ['COL_','REFL_']:
            # Note: The following two attempts to set sRGB color space are
            #       likely wrong and useless. Yet, I can not prove that these have
            #       not been working with older RS versions. As they do no harm either
            #       (just writing some unused string into a BaseContainer), I decided
            #       to leave these lines in.
            Node[c4d.REDSHIFT_FILE_COLORSPACE] = 'sRGB'
            try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_COLORSPACE] = 'sRGB'
            except : pass
            # This is how the colospace is actually set nowadays (tested in C4D 2023.1 with Redshift 3.5.13)
            try: Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0, c4d.REDSHIFT_FILE_COLORSPACE] = "RS_INPUT_COLORSPACE_SRGB"
            except Exception as e: pass

            try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_GAMMA] = 1.0
            except : pass

        elif MAP in ['AO_','SSS_','NRM_','NRM16_']:
            # See above sRGB color space note, same is true here.
            Node[c4d.REDSHIFT_FILE_COLORSPACE] = 'Raw'
            try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_COLORSPACE] = 'Raw'
            except : pass
            # Effective Raw color space setting
            try: Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0, c4d.REDSHIFT_FILE_COLORSPACE] = "RS_INPUT_COLORSPACE_RAW"
            except : pass

            try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_GAMMA] = 1.0
            except : pass

        else : # BUMP_, DISP_, GLOSS_, TRANSMISSION_
            # See above sRGB color space note, same is true here.
            try : Node[c4d.REDSHIFT_FILE_COLORSPACE] = 'scene-linear Rec.2020'
            except : pass
            try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_COLORSPACE] = 'scene-linear Rec.2020'
            except : pass
            # Effective scene-linear Rec.2020 color space setting
            try: Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0, c4d.REDSHIFT_FILE_COLORSPACE] = "scene-linear Rec.2020"
            except : pass

            try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0_GAMMA] = 1.0
            except : pass

        try : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0, c4d.REDSHIFT_FILE_PATH] = (matInfo[MAP]).encode('utf-8')
        except : Node[c4d.REDSHIFT_SHADER_TEXTURESAMPLER_TEX0, c4d.REDSHIFT_FILE_PATH] = matInfo[MAP]
        if INV:
            INV_Node = NodeMaster.CreateNode(root, 1036227, None, posX+160, posY)
            INV_Node[c4d.GV_REDSHIFT_SHADER_META_CLASSNAME] = "RSMathInvColor"
            INV_Node[c4d.ID_GVBASE_COLOR] = c4d.Vector(0.788, 0.557, 0.537)
            Node.GetOutPort(0).Connect(INV_Node.GetInPort(0))
            INV_Node.GetOutPort(0).Connect(RShader.GetInPort(LINK))
            return (Node, INV_Node)
        elif RShader != None:
            Node.GetOutPort(0).Connect(RShader.GetInPort(LINK))
            return Node

    # ------------------------- #
    #        V-Ray Shader       #
    # ------------------------- #

    def CreateVrayMat(self, matInfo, workflow, matn):
        Pmaterial = matInfo['Name']
        pName = matInfo['Name']
        multiplier = self.getProjectScale()
        doc = c4d.documents.GetActiveDocument()
        #for workflow in mapDict:
            #for res in mapDict[workflow]:
                #for matn in mapDict[workflow][res]:

        # Create the material
        StandardMat = True
        pFastSSS2 = False
        #pVRay5 = doc.GetActiveRenderData()[c4d.RDATA_RENDERENGINE] == 1053272
        pVRay5 = c4d.plugins.FindPlugin(1053272) != None
        
        if pVRay5 :
            mat = c4d.BaseMaterial(1053286)
        else :
            if "SSS_" in matInfo :
                try:
                    mat = c4d.BaseMaterial(1024192)
                    pFastSSS2 = True
                except :
                    pass
            
            if not pFastSSS2 :
                try:
                    if self.GetLong(self.RENDERER) == 111: c4d.BaseMaterial(1038954111) # For Testing the old 3.4 mat
                    mat = c4d.BaseMaterial(1038954)
                    StandardMat = True
                except:
                    try: # User running a Vray version below 3.5, Use Advanced Material instead.
                        mat = c4d.BaseMaterial(1020295)
                        StandardMat = False
                    except:
                        return False

        nodeList = []

        # ---- VRay 5 Material ---- #
        
        if pVRay5 :
            print("VRay 5")
            if "ROUGHNESS_" in matInfo or "METALNESS_" in matInfo :
                mat[c4d.BRDFVRAYMTL_OPTION_USE_ROUGHNESS] = True
            
            # Color & AO ----------------------------------------------------------------------------------------------------------------------------
            
            if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) and False : # Disabled for now.
                LayerShader = c4d.BaseShader(1011123)
                LayerShader.SetName("COLOR + AO")
                mat[c4d.BRDFVRAYMTL_DIFFUSE_TEXTURE] = LayerShader
                '''
                if "ALPHAMASKED_" in matInfo : 
                    if "MASK_" in matInfo and "SSS_" in matInfo :
                        COL_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "COL_", "COLOR", 4130, False) # 72354585
                    else :
                        COL_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "ALPHAMASKED_", "COLOR", 4130, False) # 72354585
                else :
                    COL_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "COL_", "COLOR", 4130, False) # 72354585
                
                AO_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "AO_", "AO", 4098, False)
                LayerShader[4101] = c4d.TEXLAYEREDMAX_BLEND_MODES_MULTIPLY
                LayerShader[4102] = 0.3
                '''
            else:
                COL_NODE = self.CreateVrayBitMap(mat, matInfo, "COL_", "COLOR", c4d.BRDFVRAYMTL_DIFFUSE_TEXTURE, False)
            
            # Reflection ----------------------------------------------------------------------------------------------------------------------------
            
            if "REFL_" in matInfo :
                REFL_NODE = self.CreateVrayBitMap(mat, matInfo, "REFL_", "REFLECTION", c4d.BRDFVRAYMTL_REFLECT_TEXTURE, False)
            
            # Gloss ----------------------------------------------------------------------------------------------------------------------------
            
            if "GLOSS_" in matInfo :
                GLOSS_NODE = self.CreateVrayBitMap(mat, matInfo, "GLOSS_", "GLOSS", c4d.BRDFVRAYMTL_REFLECT_GLOSSINESS_TEXTURE, False)
                GLOSS_NODE[c4d.BITMAPBUFFER_TRANSFER_FUNCTION] = c4d.BITMAPBUFFER_TRANSFER_FUNCTION_LINEAR
                
                mat[c4d.BRDFVRAYMTL_FRESNEL_IOR_LOCK] = False
                mat[c4d.BRDFVRAYMTL_FRESNEL_IOR_VALUE] = 1.45
            
            # Roughness ----------------------------------------------------------------------------------------------------------------------------
            
            if "ROUGHNESS_" in matInfo :
                ROUGH_NODE = self.CreateVrayBitMap(mat, matInfo, "ROUGHNESS_", "ROUGHNESS", c4d.BRDFVRAYMTL_REFLECT_GLOSSINESS_TEXTURE, False)
                ROUGH_NODE[c4d.BITMAPBUFFER_TRANSFER_FUNCTION] = c4d.BITMAPBUFFER_TRANSFER_FUNCTION_LINEAR
            
            # Metalness ----------------------------------------------------------------------------------------------------------------------------
            
            if "METALNESS_" in matInfo :
                MTL_NODE = self.CreateVrayBitMap(mat, matInfo, "METALNESS_", "METALNESS", c4d.BRDFVRAYMTL_METALNESS_TEXTURE, False)
                MTL_NODE[c4d.BITMAPBUFFER_TRANSFER_FUNCTION] = c4d.BITMAPBUFFER_TRANSFER_FUNCTION_LINEAR
            
            # NRM ----------------------------------------------------------------------------------------------------------------------------
            
            if "NRM16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
                NRM_Node = self.CreateVrayBitMap(mat, matInfo, "NRM16_", "NORMALS", c4d.BRDFVRAYMTL_BUMP_MAP, False)
                NRM_Node[c4d.BITMAPBUFFER_TRANSFER_FUNCTION] = c4d.BITMAPBUFFER_TRANSFER_FUNCTION_LINEAR
            elif "NRM_" in matInfo :
                NRM_Node = self.CreateVrayBitMap(mat, matInfo, "NRM_", "NORMALS", c4d.BRDFVRAYMTL_BUMP_MAP, False)
                NRM_Node[c4d.BITMAPBUFFER_TRANSFER_FUNCTION] = c4d.BITMAPBUFFER_TRANSFER_FUNCTION_LINEAR
            
            # Mask ----------------------------------------------------------------------------------------------------------------------------
            
            if "MASK_" in matInfo :
                AlphaShader = self.CreateVrayBitMap(mat, matInfo, "MASK_", "MASK", c4d.BRDFVRAYMTL_OPACITY_COLOR_TEXTURE, False)
                
            elif "ALPHAMASKED_" in matInfo :
                AlphaShader = self.CreateVrayBitMap(mat, matInfo, "ALPHAMASKED_", "ALPHAMASKED", c4d.BRDFVRAYMTL_OPACITY_COLOR_TEXTURE, False)
                
            elif "ALPHAMASKED" in matInfo["COL_"] :
                AlphaShader = self.CreateVrayBitMap(mat, matInfo, "COL_", "ALPHAMASKED", c4d.BRDFVRAYMTL_OPACITY_COLOR_TEXTURE, False)
            
            # Transmission ----------------------------------------------------------------------------------------------------------------------------
            
            if "TRANSMISSION_" in matInfo :
                TransmissionShader = self.CreateVrayBitMap(mat, matInfo, "TRANSMISSION_", "TRANSMISSION", c4d.BRDFVRAYMTL_REFRACT_TEXTURE, False)
                mat[c4d.BRDFVRAYMTL_REFRACT_GLOSSINESS_TEXTURE] = GLOSS_NODE
                mat[c4d.BRDFVRAYMTL_FOG_COLOR_TEX_TEXTURE] = COL_NODE
                mat[c4d.BRDFVRAYMTL_FOG_BIAS] = 10
            
            # SSS ----------------------------------------------------------------------------------------------------------------------------
            
            mat[c4d.BRDFVRAYMTL_BUMP_AMOUNT_MIXTYPE] = c4d.BRDFVRAYMTL_BUMP_AMOUNT_MIXTYPE_ADD
            mat[c4d.BRDFVRAYMTL_BUMP_TYPE] = c4d.BRDFVRAYMTL_BUMP_TYPE_NORMAL_MAP_IN_TANGENT_SPACE
        
        # ---- Standard Material ---- #

        elif StandardMat:
            print("Standard")
            # Color & AO ----------------------------------------------------------------------------------------------------------------------------
            
            if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1):
                LayerShader = c4d.BaseList2D(1026701)
                LayerShader.SetName("COLOR + AO")
                LayerShader[c4d.VRAY_SHADERS_LIST] = 65 # 40
                if pFastSSS2 :
                    mat[c4d.VRAYFASTSSS2MATERIAL_SSS_DIFFUSECOLORSHADER] = LayerShader
                else :
                    mat[c4d.VRAYSTDMATERIAL_DIFFUSECOLOR_TEX] = LayerShader
                mat.InsertShader(LayerShader)
                #Layered[72354585](c4d.VRAY_TEXLAYERED_COPY_BUTTON)
                if "ALPHAMASKED_" in matInfo : 
                    if "MASK_" in matInfo and "SSS_" in matInfo :
                        COL_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "COL_", "COLOR", 209847397, False) # 72354585
                    else :
                        COL_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "ALPHAMASKED_", "COLOR", 209847397, False) # 72354585
                else :
                    COL_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "COL_", "COLOR", 209847397, False) # 72354585
                AO_NODE = self.CreateVrayBitMap(LayerShader, matInfo, "AO_", "AO", 209847497, False) # 72354586
                nodeList.append(AO_NODE)
                LayerShader[209663112] = 3

                #Layered[c4d.ID_SW_TEXTURES 1_72354585]
            else:
                if pFastSSS2 :
                    if "ALPHAMASKED_" in matInfo : 
                        if "MASK_" in matInfo and "SSS_" in matInfo :
                            COL_NODE = self.CreateVrayBitMap(mat, matInfo, "COL_", "COLOR", c4d.VRAYFASTSSS2MATERIAL_SSS_DIFFUSECOLORSHADER, False)
                        else :
                            COL_NODE = self.CreateVrayBitMap(mat, matInfo, "ALPHAMASKED_", "COLOR", c4d.VRAYFASTSSS2MATERIAL_SSS_DIFFUSECOLORSHADER, False)
                    else :
                        COL_NODE = self.CreateVrayBitMap(mat, matInfo, "COL_", "COLOR", c4d.VRAYFASTSSS2MATERIAL_SSS_DIFFUSECOLORSHADER, False)
                else :
                    COL_NODE = self.CreateVrayBitMap(mat, matInfo, "COL_", "COLOR", c4d.VRAYSTDMATERIAL_DIFFUSECOLOR_TEX, False)
            
            if pFastSSS2 :
                mat[c4d.VRAYFASTSSS2MATERIAL_SSS_DIFFUSEAMOUNT] = 1
            

            # Reflection ----------------------------------------------------------------------------------------------------------------------------
            
            if pFastSSS2 :
                pass
            else :
                mat[c4d.VRAYSTDMATERIAL_REFLECTAFFECTCHANNELS] = 2
            
            if "REFL_" in matInfo:
                if workflow == "DIALECTRIC":
                    if pFastSSS2 :
                        REFL_NODE = self.CreateVrayBitMap(mat, matInfo, "REFL_", "REFLECTION", c4d.VRAYFASTSSS2MATERIAL_SSS_SPECULARCOLORSHADER, True)
                    else :
                        REFL_NODE = self.CreateVrayBitMap(mat, matInfo, "REFL_", "REFLECTION", c4d.VRAYSTDMATERIAL_REFLECTCOLOR_TEX, True)
                        mat[c4d.VRAYSTDMATERIAL_REFLECTFRESNELIOR_LOCK] = False
                    REFL_NODE[c4d.VRAY_BITMAPCCGAMMA_BB_GAIN_FAKE] = 0.6
                else:
                    if pFastSSS2 :
                        REFL_NODE = self.CreateVrayBitMap(mat, matInfo, "REFL_", "REFLECTION", c4d.VRAYFASTSSS2MATERIAL_SSS_SPECULARCOLORSHADER, True)
                    else :
                        REFL_NODE = self.CreateVrayBitMap(mat, matInfo, "REFL_", "REFLECTION", c4d.VRAYSTDMATERIAL_REFLECTCOLOR_TEX, False)
                        mat[c4d.VRAYSTDMATERIAL_REFLECTFRESNEL] = False
            
            if pFastSSS2 :
                mat[c4d.VRAYFASTSSS2MATERIAL_SSS_SPECULARTRACE] = True
            else :
                mat[c4d.VRAYSTDMATERIAL_REFLECTCOLOR] = c4d.Vector(1,1,1)


            # Gloss ----------------------------------------------------------------------------------------------------------------------------
            
            if pFastSSS2 :
                GLOSS_NODE = self.CreateVrayBitMap(mat, matInfo, "GLOSS_", "GLOSS", c4d.VRAYFASTSSS2MATERIAL_SSS_SPECULARGLOSSINESSSHADER, False)
                mat[c4d.VRAYFASTSSS2MATERIAL_SSS_SPECULARGLOSSINESS] = 1
            else :
                GLOSS_NODE = self.CreateVrayBitMap(mat, matInfo, "GLOSS_", "GLOSS", c4d.VRAYSTDMATERIAL_REFLECTGLOSSINESS_TEX, False)
                mat[c4d.VRAYSTDMATERIAL_REFLECTFRESNELIOR_LOCK] = False # Lock IOR
            GLOSS_NODE[c4d.VRAY_BITMAPCCGAMMA_BB_COLOR_SPACE] = 0
            GLOSS_NODE[c4d.VRAY_BITMAPCCGAMMA_BB_GAMMA] = 1


            # NRM ----------------------------------------------------------------------------------------------------------------------------
            
            if "NRM16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
                if pFastSSS2 :
                    NRM_Node = self.CreateVrayBitMap(mat, matInfo, "NRM16_", "NORMALS", c4d.VRAYFASTSSS2MATERIAL_SSS_BUMP_SHADER, False)
                else :
                    NRM_Node = self.CreateVrayBitMap(mat, matInfo, "NRM16_", "NORMALS", c4d.VRAYSTDMATERIAL_BUMP_NORMALMAP, False)
            else:
                if pFastSSS2 :
                    NRM_Node = self.CreateVrayBitMap(mat, matInfo, "NRM_", "NORMALS", c4d.VRAYFASTSSS2MATERIAL_SSS_BUMP_SHADER, False)
                else :
                    NRM_Node = self.CreateVrayBitMap(mat, matInfo, "NRM_", "NORMALS", c4d.VRAYSTDMATERIAL_BUMP_NORMALMAP, False)
            
            if pFastSSS2 :
                mat[c4d.VRAYFASTSSS2MATERIAL_SSS_USE_BUMP] = 1
                mat[c4d.VRAYFASTSSS2MATERIAL_SSS_BUMP_TYPE] = 1
            else :
                mat[c4d.VRAYSTDMATERIAL_BUMP_TYPE] = 1
                mat[c4d.VRAYSTDMATERIAL_BUMP_FLIPGREEN] = True


            #Alphamasked ----------------------------------------------------------------------------------------------------------------------------
            
            if "MASK_" in matInfo and not pFastSSS2 :
                AlphaShader = self.CreateVrayBitMap(mat, matInfo, "MASK_", "MASK", c4d.VRAYSTDMATERIAL_OPACITY_TEX, False)
                nodeList.append(AlphaShader)
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_COLORCORRECTION_ENABLE] = True
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_CC_REWIRE_RED] = 3
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_CC_REWIRE_GREEN] = 3
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_CC_REWIRE_BLUE] = 3

            elif "ALPHAMASKED_" in matInfo and not pFastSSS2 :
                AlphaShader = self.CreateVrayBitMap(mat, matInfo, "ALPHAMASKED_", "ALPHAMASKED", c4d.VRAYSTDMATERIAL_OPACITY_TEX, False)
                nodeList.append(AlphaShader)
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_COLORCORRECTION_ENABLE] = True
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_CC_REWIRE_RED] = 3
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_CC_REWIRE_GREEN] = 3
                AlphaShader[c4d.VRAY_BITMAPCCGAMMA_CC_REWIRE_BLUE] = 3


            # Transmission ----------------------------------------------------------------------------------------------------------------------------
            
            if "TRANSMISSION_" in matInfo and not pFastSSS2 :
                TransmissionShader = self.CreateVrayBitMap(mat, matInfo, "TRANSMISSION_", "TRANSMISSION", c4d.VRAYSTDMATERIAL_REFRACTCOLOR_TEX, False)
                nodeList.append(TransmissionShader)
                mat[c4d.VRAYSTDMATERIAL_REFRACTGLOSSINESS_TEX] = GLOSS_NODE
                mat[c4d.VRAYSTDMATERIAL_FOGCOLOR_TEX] = COL_NODE
                mat[c4d.VRAYSTDMATERIAL_FOGBIAS] = 10
                #GLOSS_NODE = self.CreateVrayBitMap(mat, matInfo, "GLOSS_", "GLOSS", c4d.VRAYSTDMATERIAL_REFRACTGLOSSINESS_TEX, False)
                #GLOSS_NODE[c4d.VRAY_BITMAPCCGAMMA_BB_COLOR_SPACE] = 0
                #GLOSS_NODE[c4d.VRAY_BITMAPCCGAMMA_BB_GAMMA] = 1
                #mat[c4d.VRAYSTDMATERIAL_REFLECTFRESNELIOR_LOCK] = False # Lock IOR


            # SSS ----------------------------------------------------------------------------------------------------------------------------
            
            if "SSS_" in matInfo :
                if pFastSSS2 : 
                    SSSShader = self.CreateVrayBitMap(mat, matInfo, "SSS_", "Subsurface Scattering", c4d.VRAYFASTSSS2MATERIAL_SSS_SSSCOLORSHADER, False)
                    mat[c4d.VRAYFASTSSS2MATERIAL_SSS_SCATTERSHADER] = SSSShader
                    
                    #SSSShader1 = self.CreateVrayBitMap(mat, matInfo, "SSS_", "Subsurface Scattering 1", c4d.VRAYFASTSSS2MATERIAL_SSS_SSSCOLORSHADER, True)
                else :
                    mat[c4d.VRAYSTDMATERIAL_REFRACTCOLOR] = c4d.Vector(0.169, 0.169, 0.169)
                    mat[c4d.VRAYSTDMATERIAL_REFRACTGLOSSINESS] = 0
                    mat[c4d.VRAYSTDMATERIAL_TRANSLUCENCY] = 1
                    mat[c4d.VRAYSTDMATERIAL_TRANSLUCENCYTHICKNESS] = 1
                    SSSShader = self.CreateVrayBitMap(mat, matInfo, "SSS_", "Subsurface Scattering", c4d.VRAYFASTSSS2MATERIAL_SSS_DIFFUSEAMOUNTSHADER, False)
                nodeList.append(SSSShader)
                
                if "ALPHAMASKED_" in matInfo and "MASK_" in matInfo :
                    mat2 = c4d.BaseMaterial(1038954)
                    mat2[c4d.VRAYSTDMATERIAL_OPACITY] = 0
                    mat2.SetName(matInfo['Name']+'_OP')
                    doc.InsertMaterial(mat2)
                    
                    matb = c4d.BaseMaterial(1022116)
                    matb.SetName(matInfo['Name'])
                    doc.InsertMaterial(matb)
                    matb[c4d.VRAYBLENDMATERIAL_PARAMS_USELINK10] = True
                    matb[c4d.VRAYBLENDMATERIAL_PARAMS_LINK10] = mat2
                    matb[c4d.VRAYBLENDMATERIAL_PARAMS_USELINK1] = True
                    matb[c4d.VRAYBLENDMATERIAL_PARAMS_LINK1] = mat
                    MASKShader = self.CreateVrayBitMap(matb, matInfo, "MASK_", "Mask", c4d.VRAYBLENDMATERIAL_PARAMS_WEIGHTTEXLINK1, False)
                    
                    pName = matInfo['Name']+'_SSS'

        # ---- Advanced Material ---- #

        else:
            print("Advanced")
            # Load Color / AO ----------------------------------------------------------------------------------------------------------------------------
            
            if "AO_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+1) and workflow == 'DIALECTRIC':
                Fusion_shader = c4d.BaseList2D(c4d.Xfusion)
                Fusion_shader.SetName("COLOR + AO")
                self.Create_Bitmap(Fusion_shader, matInfo, "COL_", "COLOR", c4d.SLA_FUSION_BASE_CHANNEL, False)
                self.Create_Bitmap(Fusion_shader, matInfo, "AO_", "AMBIENT OCCLUSION", c4d.SLA_FUSION_BLEND_CHANNEL, False)
                Fusion_shader[c4d.SLA_FUSION_MODE] = 2019
                #mat[c4d.VRAYMATERIAL_COLOR1_TEXTUREMIXMODE] = 6
                mat[c4d.VRAYMATERIAL_COLOR1_SHADER] = Fusion_shader
                mat.InsertShader(Fusion_shader)
            else:
                self.Create_Bitmap(mat, matInfo, "COL_", "COLOLR", c4d.VRAYMATERIAL_COLOR1_SHADER, False)


            # Reflection ----------------------------------------------------------------------------------------------------------------------------
            
            mat[c4d.VRAYMATERIAL_SPECULAR1_MODE] = 3
            mat[c4d.VRAYMATERIAL_USE_SPECULAR1] = True
            if "REFL_" in matInfo:
                if workflow == "DIALECTRIC":
                    self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", c4d.VRAYMATERIAL_SPECULAR1_SHADER, True)
                else:
                    self.Create_Bitmap(mat, matInfo, "REFL_", "REFLECTION", c4d.VRAYMATERIAL_SPECULAR1_SHADER, False)
                    self.Create_Bitmap(mat, matInfo, "COL_", "COLOR", c4d.VRAYMATERIAL_SPECULAR1_FRESNELREFLSHADER, False)
                    mat[c4d.VRAYMATERIAL_SPECULAR1_FRESNELIOR1] = 0


            # GLOSS ----------------------------------------------------------------------------------------------------------------------------
            
            self.Create_Bitmap(mat, matInfo, "GLOSS_", "GLOSS", c4d.VRAYMATERIAL_SPECULAR1_REFLECTIONGLOSSSHADER, False)


            # Normals ----------------------------------------------------------------------------------------------------------------------------
            
            mat[c4d.VRAYMATERIAL_USE_BUMP] = True
            mat[c4d.VRAYMATERIAL_BUMP_TYPE] = 1
            #mat[c4d.VRAYMATERIAL_BUMP_BUMPTEXINVERT_R] = True
            if "NRM16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
                NRM_Node = self.Create_Bitmap(mat, matInfo, "NRM16_", "NORMALS", c4d.VRAYMATERIAL_BUMP_SHADER, False)
            else:
                NRM_Node = self.Create_Bitmap(mat, matInfo, "NRM_", "NORMALS", c4d.VRAYMATERIAL_BUMP_SHADER, False)
            # ALPHAMASKED
            #if "ALPHAMASKED_" in matInfo:
            #    self.Create_Bitmap(mat, matInfo, "ALPHAMASKED_", "ALPHAMASKED", c4d.VRAYMATERIAL_WEIGHT_SHADER, False)
        
        if not pVRay5 :
            # Mask Blend ----------------------------------------------------------------------------------------------------------------------------
            
            if c4d.plugins.FindPlugin(1022116) != None :
                if "MASK_" in matInfo or "ALPHAMASKED_" in matInfo :
                    BlendMat = c4d.BaseMaterial(1022116)
                    BlendMat.SetName((matn+"_Blend"))
                    BlendMat[c4d.VRAYBLENDMATERIAL_PARAMS_USELINK1] = True
                    BlendMat[c4d.VRAYBLENDMATERIAL_PARAMS_LINK1] = mat
                    BlendMat[c4d.VRAYBLENDMATERIAL_PARAMS_USELINK10] = False
                    
                    if "MASK_" in matInfo : mType = "MASK"
                    elif "ALPHAMASKED_" in matInfo : mType = "ALPHAMASKED"
                    
                    MaskMat = self.Create_Bitmap(BlendMat, matInfo, mType+"_", mType, c4d.VRAYBLENDMATERIAL_PARAMS_WEIGHTTEXLINK1, False)
                    
                    doc.InsertMaterial(BlendMat)

            # Displacement ----------------------------------------------------------------------------------------------------------------------------
            
            # Displacements (for both standard and advanced material)
            if self.GetBool(id=self.ADVANCED_SETTINGS+2) and ("DISP_" in matInfo or ("DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4))):
                Dispmat = c4d.BaseMaterial(1022593)
                Dispmat.SetName((matn+"_Displacement"))
                Dispmat[c4d.VRAYDISPLACEMATERIAL_TYPE] = 1
                Dispmat[c4d.VRAYDISPLACEMATERIAL_AMOUNT] = 0.5*multiplier

                if "DISP16_" in matInfo and self.GetBool(id=self.ADVANCED_SETTINGS+4):
                    DISP_NODE = self.CreateVrayBitMap(Dispmat, matInfo, "DISP16_", "DISPLACEMENT", c4d.VRAYDISPLACEMATERIAL_TEXTURE, False) # Might need to use old disp
                else:
                    DISP_NODE = self.CreateVrayBitMap(Dispmat, matInfo, "DISP_", "DISPLACEMENT", c4d.VRAYDISPLACEMATERIAL_TEXTURE, False)
                DISP_NODE[c4d.VRAY_BITMAPCCGAMMA_BB_COLOR_SPACE] = 0
                nodeList.append(DISP_NODE)
                Dispmat.Update(True, True)
                doc.InsertMaterial(Dispmat)

        # Conform UV Maps
        if self.GetBool(id=self.ADVANCED_SETTINGS+3) and StandardMat:
            u, v = self.ConformUVMap(matInfo["COL_"])
            nodeList += [COL_NODE, REFL_NODE, GLOSS_NODE, NRM_Node]
            for node in nodeList:
                node[c4d.VRAY_BITMAPCCGAMMA_W] = u
                node[c4d.VRAY_BITMAPCCGAMMA_H] = v

        mat.SetName(pName)
        return mat

    # Import VRay5 Layer from template
    def p_AddVray5Layer(self, pMat, pLink) :
        doc = c4d.documents.GetActiveDocument()
        
        pMats = doc.GetMaterials()
        c4d.documents.MergeDocument(doc, os.path.join(PLUGIN_PATH, "res", "templates", "poliigon_vray5_layers.c4d"), c4d.SCENEFILTER_MATERIALS, None)
        pTemp = [pM for pM in doc.GetMaterials() if pM not in pMats][0]
        
        pData = pTemp.GetData()
        pLyr = pData[605015197]
        
        pMat[pLink] = pLyr
        pMat.InsertShader(pLyr)
        
        pTemp.Remove()
        
        return pLyr
    
    # Create a vray bitmap
    def CreateVrayBitMap(self, mat, matInfo, MAP, NAME, LINK, INV):
        try :
            shader = c4d.BaseList2D(1055619) # VRay5
            pFileID = c4d.BITMAPBUFFER_FILE
            pInvID = c4d.TEXBITMAP_INVERT
        except :
            shader = c4d.BaseList2D(1037364)
            pFileID = c4d.VRAY_BITMAPCCGAMMA_BITMAP_FILENAME
            pInvID = c4d.VRAY_BITMAPCCGAMMA_INVERT
        
        try : shader[pFileID] = (matInfo[MAP]).encode('utf-8')
        except : shader[pFileID] = matInfo[MAP]
        
        if INV: shader[pInvID] = True
        shader.SetName(NAME)
        
        if LINK != None : mat[LINK] = shader
        
        mat.InsertShader(shader)
        return shader


    # Create Preview Spheres
    def CreatePreviewSpheres(self, mapList):
        SpherePos = (((self.nMats*250)/2)-125)*-1
        rEngine = self.GetLong(self.RENDERER)
        for mat in mapList:
            matname = mat.GetName()
            doc = c4d.documents.GetActiveDocument()
            sphere = c4d.BaseObject(c4d.Osphere)
            try:
                sphere[c4d.ID_BASELIST_NAME] = matname.encode('utf-8')
            except:
                sphere[c4d.ID_BASELIST_NAME] = matname
            doc.InsertObject(sphere)
            c4d.CallCommand(100004767, 100004767)
            sphere.SetBit(c4d.BIT_ACTIVE)
            sphere[c4d.PRIM_SPHERE_SUB] = 64
            matlist = doc.GetMaterials()
            for matl in matlist:
                if matname == matl.GetName():
                    textag = c4d.TextureTag()
                    textag.SetMaterial(matl)
                    sphere.InsertTag(textag)
                    if rEngine in [1019782,111,1053272]: # VRay
                        for matd in matlist:
                            if (matname + " Displacement") == matd.GetName():
                                textag = c4d.TextureTag()
                                textag.SetMaterial(matd)
                                sphere.InsertTag(textag)
            sphere.InsertTag(c4d.BaseTag(c4d.Tphong))
            sphere.SetAbsPos(c4d.Vector(SpherePos,0,0))
            SpherePos+=250
            if rEngine == 1029988: # Arnold
                m = self.getProjectScale()
                tag = c4d.BaseTag(1029989)
                sphere.InsertTag(tag)
                tag[486485632] = True
                tag[1039494868] = (2*m)
                tag[1635638890] = 1
                tag[408131505] = 0


    # ------------------------- #
    #    Internal Operations    #
    # ------------------------- #

    # Search through the light_setups dir for any maya files, and add them to the dropdown list (internal only)
    def getLightsetups(self):
        SCRIPT_PATH = os.path.split(__file__)[0]
        SCRIPT_PATH = os.path.join(SCRIPT_PATH, "light_setups")
        if not os.path.exists(SCRIPT_PATH):
            os.makedirs(SCRIPT_PATH)
            return False
        i = 1
        for root, dirs, files in os.walk(SCRIPT_PATH): # Search the root for files
            for name in files:
                if os.path.splitext(name)[1] == ".c4d":
                    self.LightSetups[name] = os.path.join(root, name)
                    self.LightSetups_i.append((name, i))
                    i+=1
        self.LightSetups["<None>"] = None

    # Open the light_setups folder in explorer (internal only)
    def openFolder(self):
        ScriptPath = os.path.split(__file__)[0]
        LightPath = os.path.join(ScriptPath, "light_setups")
        os.startfile(LightPath)

    # Create the folder were the file will be saved
    # Copy all of the textures into that folder
    # And update the mapdict to use relative paths instead. (Internal only)
    def CreateFolder(self, matInfo, matn, engineName):
        from shutil import copyfile
        folderPath = os.path.join(self.SavePath+engineName)

        # C4D textures should be placed in a subfolder named "tex" next to the .c4d file
        if self.GetBool(id=self.ADVANCED_SETTINGS+10):
            texfolderPath = os.path.join(folderPath, "tex")
        else:
            texfolderPath = os.path.join(folderPath, "tex")

        # Create Dir
        if not os.path.isdir(texfolderPath):
            os.makedirs(texfolderPath)

        # Copy textures into the new folder and replace all filepaths with relative filepaths
        matInfot = {}
        for texture in matInfo:
            if texture != "Name":
                texturePath = matInfo[texture]
                texName =  os.path.split(texturePath)[1]
                newTexturePath = os.path.join(texfolderPath, texName)
                copyfile(texturePath, newTexturePath)
                matInfot.update({texture:texName})

        # Open the light setup file selected, and then it will be saved out as a new file
        if not self.ImportedLights:
            LSetup = self.GetLong(self.LIGHT_SETUP)
            if LSetup != 0:
                for ls in self.LightSetups_i:
                    if ls[1] == LSetup:
                        fpath = self.LightSetups[ls[0]]
                        c4d.documents.LoadFile(fpath)
                        self.ImportedLights = True


        return matInfot

    # Save the file and create a new one (internal only)
    def SaveFile(self, engineName):
        folderPath = os.path.join(self.SavePath+engineName)
        FileP = os.path.join(folderPath, self.SceneName+"_"+engineName+".c4d")
        doc = c4d.documents.GetActiveDocument()

        # Save file
        #c4d.documents.SaveDocument(doc, (FileP).encode('utf-8'), c4d.SAVEDOCUMENTFLAGS_0, c4d.FORMAT_C4DEXPORT)
        c4d.documents.SaveDocument(doc, FileP, c4d.SAVEDOCUMENTFLAGS_0, c4d.FORMAT_C4DEXPORT)

        # New scene
        c4d.CallCommand(12094, 12094)

    # Import models related to the created texture (Internal only)
    def ImportModel(self, mat, matn):
        rEngine = self.GetLong(self.RENDERER)
        doc = c4d.documents.GetActiveDocument()
        m = self.getProjectScale()
        for obj in self.OBJlist:
            if matn == os.path.basename(obj).split('.')[0]:
                # Import the model

                preObjs = doc.GetObjects()
                #c4d.documents.MergeDocument(doc, (obj).encode('utf-8'), c4d.SCENEFILTER_OBJECTS, None)
                c4d.documents.MergeDocument(doc, obj, c4d.SCENEFILTER_OBJECTS, None)
                postObj = doc.GetObjects()

                # Figure out which models was just imported by comparing the scene objects before and after
                models = []
                for iobj in postObj:
                    if iobj not in preObjs:
                        models.append(iobj)

                # Add some properties to each model
                for model in models:

                    # If the model was imported from an obj, scale up by 100 units
                    if "obj" == os.path.basename(obj).split('.')[1]:
                        model[c4d.ID_BASEOBJECT_FROZEN_SCALE] = c4d.Vector(100, 100, 100)

                    # Apply the material to the model
                    tag = model.GetTag(c4d.Ttexture)
                    if tag == None:
                        tag = c4d.TextureTag()
                        tag.SetMaterial(mat)
                        model.InsertTag(tag)
                    else:
                        tag.SetMaterial(mat)
                    tag[c4d.TEXTURETAG_PROJECTION] = 6

                    matlist = doc.GetMaterials()

                    # Engine Spesific Tags

                    # Vray
                    if rEngine in [1019782,111,1053272]:
                        for matl in matlist:
                            if (mat.GetName()+"_Displacement") == matl.GetName():
                                tag = c4d.TextureTag()
                                tag.SetMaterial(matl)
                                model.InsertTag(tag)

                    # Redshift
                    elif rEngine == 1036219:
                        Rtag = c4d.BaseTag(1036222)
                        model.InsertTag(Rtag)

                     # Arnold
                    elif rEngine == 1029988:
                        multiplier = self.getProjectScale()
                        Atag = c4d.BaseTag(1029989)
                        Atag[408131505] = self.PatchTransmission
                        Atag[1039494868] = .1*multiplier
                        Atag[1635638890] = 1
                        Atag[486485632] = True
                        model.InsertTag(Atag)

                    # Octane
                    elif rEngine == 1029525:
                        Otag = c4d.BaseTag(1029603)
                        model.InsertTag(Otag)


# Custom exception hook to catch any uncaught errors and print them to the user in a messagebox
def PMCExceptionHook(etype, value, tb, detail=2):

    # Start by turning off the custom exceptionhook,
    # then incase anything below gives an error, it won't get stuck in a loop.
    TogglePMCExceptionHook(False)

    try: traceback
    except: import traceback

    # Stop the status bar
    c4d.StatusClear()

    ErrorMsg = traceback.format_exception(etype, value, tb)
    # Add some releavnt system info to the message

    # Get the render engine the user is tring to convert too
    try:
        # dialog.RENDERER might not exist yet incase the error occured before it's created.
        rEngine = dialog.GetLong(dialog.RENDERER)
    except:
        rEngine = "undefined"
    Engines = {
        '1029988': "Arnold",
        '1030480': "Corona",
        '1029525': "Octane",
        '0': "Physical",
        '1036219': "Redshift",
        '1019782': "V-Ray",
        '1053272': "V-Ray",
        '1037639': "ProRender"
    }
    if str(rEngine) in Engines: Engine = Engines[str(rEngine)]
    else: Engine = rEngine

    # Get the plugin version of that renderer
    # So far I've only figured out how to get the version for Arnold & Corona,
    # But it'd be a good idea to look into this later and see how you get
    # the plugin versions for all of the other supported renderers.
    if Engine == "Arnold":
        doc = c4d.documents.GetActiveDocument()
        arnoldSceneHook = doc.FindSceneHook(1032309)
        msg = c4d.BaseContainer()
        msg.SetInt32(1000, 1040)
        arnoldSceneHook.Message(c4d.MSG_BASECONTAINER, msg)
        PluginVersion = msg.GetString(2011)
    elif Engine == "Corona":
        import corona
        PluginVersion = str(corona.versionNumber)
    #elif Engine == "Redshift":
    #    PluginVersion = str(Redshift[c4d.PREFS_REDSHIFT_REDSHIFT_VERSION])
    else:
        PluginVersion = ""

    SysInfo = 'Tool: Poliigon Material Converter v' + PMCversion +\
    '\nCinema 4D: ' + str(C4D_version) +\
    '\nRenderer: ' + Engine + ' ' + PluginVersion +\
    '\nOS: ' + sys.platform
    '\nMaterial: ' + Pmaterial

    msg = SysInfo + "\n"
    for line in ErrorMsg:
        msg += line

    # Print the message to the console
    print (msg)

    # Open up the error dialog
    global ErrorDialog
    ErrorDialog = PMCErrorMessage()
    ErrorDialog.msg = msg
    ErrorDialog.Open(dlgtype=c4d.DLG_TYPE_ASYNC, pluginid=PLUGIN_ID, defaultw=600, defaulth=200, subid=2)

    return traceback.format_exception(etype, value, tb, 3)


# Toggle the custom exception hook on/off
def TogglePMCExceptionHook(state):
    if state:
        sys.excepthook = PMCExceptionHook
    else:
        sys.excepthook = DefaultExceptionHook


# Dialog to display the error message
class PMCErrorMessage(c4d.gui.GeDialog):

    msg = ""

    BUTTON_DISMISS = 1100
    MESSAGE_FIELD = 1102

    def CreateLayout(self):
        self.SetTitle(c4d.plugins.GeLoadString(4000))

        # UI

        # Texture Folder & Renderer
        self.GroupBegin(id=80, flags=c4d.BFH_LEFT, rows=2, title="", cols=1)
        self.GroupBorderSpace(5,5,0,5)
        self.AddStaticText(id=85, flags=c4d.BFH_LEFT, initw=600, name=c4d.plugins.GeLoadString(4001))
        self.AddStaticText(id=86, flags=c4d.BFH_LEFT, initw=700, name=c4d.plugins.GeLoadString(4002))
        self.GroupEnd()

        self.GroupBegin(id=81, flags=c4d.BFH_SCALEFIT | c4d. BFV_SCALEFIT, rows=1, title="", cols=1)
        self.GroupBorderSpace(5,0,5,5)
        self.AddMultiLineEditText(self.MESSAGE_FIELD, flags=c4d.BFH_SCALEFIT | c4d. BFV_SCALEFIT, initw=700, inith=150, style=c4d.DR_MULTILINE_READONLY)
        self.GroupEnd()

        self.GroupBegin(id=82, flags=c4d.BFH_SCALEFIT, rows=1, title="", cols=2)
        self.GroupBorderSpace(5,0,5,10)

        self.GroupBegin(id=82, flags=c4d.BFH_RIGHT, rows=1, title="", cols=2)
        self.AddButton(id=self.BUTTON_DISMISS, flags=c4d.BFH_RIGHT, initw=60, inith=20, name=c4d.plugins.GeLoadString(4004))
        self.GroupEnd()

        self.GroupEnd()

        # Set the error message
        self.SetString(id=self.MESSAGE_FIELD, value=self.msg)

        return True

    def Command(self, id, msg, what=False):
        # BUTTON: Dismiss
        if id==self.BUTTON_DISMISS:
            self.Close()

        return True
