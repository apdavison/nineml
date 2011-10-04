from ZODB.FileStorage import FileStorage
from ZODB.DB import DB
storage = FileStorage('zodb/nineml-webapp.zodb')
db = DB(storage)
connection = db.open()
root = connection.root()

"""
['pdfReport']
['zipReport']
['tests_data']
['inspector']
['nineml_component']
['environ']
"""

for key in root:
    print(' environ: {0}'.format(root[key]['environ']))

