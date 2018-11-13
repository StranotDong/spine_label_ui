class nameRules:
    def __init__(self):
        # edit/view mode
        self.edit = 'edit'
        self.view = 'view'
        
        # temp_file
        self.temp_filename = '.usrnm'

        # vb list
        self.VBLabelList = ['S1', 'L5','L4','L3','L2','L1', \
                           'T12','T11','T10','T9','T8','T7',\
                           'T6','T5','T4','T3']

        # coordinate types
        self.CoordTypeList = ['cen', 'cor']

        # VBDict keys
        self.Coords = 'Coords'
        self.CorCoords = 'CorCoords'
        self.Fracture = 'Fracture'
        
        # controversial dict keys
        self.Modifier = 'Modifier'
        self.ConPart = 'ConPart'
        self.ConStatus = 'ConStatus'

        # fracture types
        self.normal = 'normal'
        self.ost = 'osteoporotic fracture'
        self.non_ost = 'non-osteoporotic deformity'

        # touch/untouch status
        self.touch = 'T'
        self.untouch = 'U'

        # contoversial status
        self.controversial = 'C'
        self.uncontroversial = 'UC'

        # readable status
        self.readable = 'R'
        self.unreadable = 'UR'

        # csv headers
        self.head_imgID = 'Image ID'
        self.head_status = 'Status'
        self.head_vbLabel = 'VB Label'
        self.head_cenX = 'Center X'
        self.head_cenY = 'Center Y'
        self.head_corX = 'Corner X'
        self.head_corY = 'Corner Y'
        self.head_frac = 'Fracture?'
        self.head_modifier = 'Last Modifier'
        self.head_conStatus = 'Controversial Status'
        self.head_conParts = 'Comments'
        self.head_readableStatus = 'Readable?'

        self.csv_headers = [self.head_imgID, self.head_status, self.head_vbLabel, self.head_cenX, self.head_cenY, self.head_corX, self.head_corY, self.head_frac, self.head_modifier, self.head_conStatus, self.head_conParts, self.head_readableStatus]

        # save status
        self.saved = 'saved'
        self.unsaved = 'unsaved'
