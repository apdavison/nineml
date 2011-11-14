#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os, httplib, urllib, json

class nineml_web_service:
    #server = "nineml-app.incf.org"
    def __init__(self, server = "localhost", port = 80):
        self.headers = {'Content-type': 'application/x-www-form-urlencoded', 
                        'User-Agent'  : 'NineML WebService Application/1.0',
                        'Accept'      : 'text/plain'}
        self.http_connection = httplib.HTTPConnection(server, port)
        self._getApplicationID()

    def __del__(self):
        self.http_connection.close()
        
    def getAvailableALComponents(self):
        parameters = {'__NINEML_ACTION__' : 'getAvailableALComponents'}
        self._sendRequest(parameters, self.headers)
        available_components = self._getResponse()
        print('available_components:\n', available_components)
        return available_components

    def setALComponent(self, testableComponentName):
        parameters = {'__NINEML_ACTION__'    : 'setALComponent',
                      '__NINEML_WEBAPP_ID__' : self.applicationID,
                      'TestableComponent'    : testableComponentName
                     }
        self._sendRequest(parameters, self.headers)
        component_name = self._getResponse()
        print('component_name:', component_name)
        return component_name
    
    def displayGUI(self, initialValues = ''):
        parameters = {'__NINEML_ACTION__'    : 'displayGUI',
                      '__NINEML_WEBAPP_ID__' : self.applicationID,
                      'InitialValues'        : initialValues
                     }
        self._sendRequest(parameters, self.headers)
        gui = self._getResponse()
        print('gui:', gui)
        return gui
    
    def generateReport(self):
        parameters = {'__NINEML_ACTION__'    : 'generateReport',
                      '__NINEML_WEBAPP_ID__' : self.applicationID
                     }
        self._sendRequest(parameters, self.headers)
        response = self._getResponse()
        print('response:', response)
        return response

    def downloadPDF(self, filename):
        parameters = {'__NINEML_ACTION__'    : 'downloadPDF',
                      '__NINEML_WEBAPP_ID__' : self.applicationID
                     }
        self._sendRequest(parameters, self.headers)
        pdf = self._getResponse()
        if pdf:
            f = open(filename, "w")
            f.write(pdf)
            f.close()

    def downloadZIP(self, filename):
        parameters = {'__NINEML_ACTION__'    : 'downloadZIP',
                      '__NINEML_WEBAPP_ID__' : self.applicationID
                     }
        self._sendRequest(parameters, self.headers)
        zip = self._getResponse()
        if zip:
            f = open(filename, "w")
            f.write(pdf)
            f.close()

    def _getApplicationID(self):
        parameters = {'__NINEML_ACTION__' : 'getApplicationID'}
        self._sendRequest(parameters, self.headers)
        self.applicationID = self._getResponse()
        print('applicationID:', self.applicationID)
        return self.applicationID

    def _sendRequest(self, dict_parameters, headers):
        parameters = urllib.urlencode(dict_parameters)
        self.http_connection.request('POST', '/nineml-webapp', parameters, headers)

    def _getResponse(self):
        response = self.http_connection.getresponse()
        if(response.status != 200):
            raise RuntimeError('The http request failed: {0} {1}'.format(response.status, response.reason))
        
        content_type = response.getheader('Content-type', '')
        print("content_type: " + content_type)
        if content_type == 'application/json':
            json_data = json.loads(response.read())
            if (not 'success' in json_data) or (not 'error' in json_data) or (not 'content' in json_data):
                raise RuntimeError('Invalid http response received')
            
            if json_data['success'] == False:
                raise RuntimeError('The error occured in NineML web application:\n' + json_data['error'])
            
            return json_data['content']
        elif content_type == 'application/pdf':
            print("application/pdf")
            return response.read()
        elif content_type == 'application/zip':
            print("application/zip")
        elif content_type == 'text/html':
            print("")
        else:
            raise RuntimeError('Unrecognized Content-type received: ' + content_type)
    
if __name__ == "__main__":
    ws = nineml_web_service()
    ws.getAvailableALComponents()
    ws.setALComponent('hierachical_iaf_1coba')
    ws.displayGUI()
    ws.generateReport()
    filename = 'pdf-report.pdf'
    ws.downloadPDF(filename)
    if os.name == 'nt':
        os.filestart(filename)
    elif os.name == 'posix':
        os.system('/usr/bin/xdg-open ' + filename)  
    
    #headers = {'Content-type': 'application/x-www-form-urlencoded', 
               #'User-Agent'  : 'NineML WebService Application/1.0',
               #'Accept'      : 'text/plain'}

    #http_connection = httplib.HTTPConnection('localhost')

    #params  = urllib.urlencode({'__NINEML_ACTION__' : 'getApplicationID'})
    #http_connection.request('POST', '/nineml-webapp', params, headers)
    #applicationID = getResponse(http_connection)
    #print('applicationID:', applicationID)

    #params  = urllib.urlencode({'__NINEML_ACTION__' : 'getAvailableALComponents'})
    #http_connection.request('POST', '/nineml-webapp', params, headers)
    #available_components = getResponse(http_connection)
    #print('available_components:\n', available_components)

    #params  = urllib.urlencode({'__NINEML_ACTION__'    : 'setALComponent',
                                #'__NINEML_WEBAPP_ID__' : applicationID,
                                #'TestableComponent'    : 'hierachical_iaf_1coba'
                                #})
    #http_connection.request('POST', '/nineml-webapp', params, headers)
    #component_name = getResponse(http_connection)
    #print('component_name:', component_name)

    #http_connection.close()