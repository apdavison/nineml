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

for key, value in root.iteritems():
    print('    {0} : {1}'.format(key, repr(value)))

