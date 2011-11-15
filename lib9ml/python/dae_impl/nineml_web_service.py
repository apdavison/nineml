#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os, httplib, urllib, json, re

class nineml_web_service:
    def __init__(self, server = 'nineml-app.incf.org', port = 80):
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
        available_components, response = self._getResponse()
        return available_components

    def setALComponent(self, testableComponentName):
        parameters = {'__NINEML_ACTION__'    : 'setALComponent',
                      '__NINEML_WEBAPP_ID__' : self.applicationID,
                      'TestableComponent'    : testableComponentName
                     }
        self._sendRequest(parameters, self.headers)
        component_name, response = self._getResponse()
        return component_name
    
    def uploadALComponent(self, xmlFile):
        f = open(xmlFile, "r")
        xml = f.read()
        f.close()

        parameters = {'__NINEML_ACTION__'    : 'uploadALComponentAsXMLString',
                      '__NINEML_WEBAPP_ID__' : self.applicationID,
                      'xmlFile'              : xml
                     }
        self._sendRequest(parameters, self.headers)
        component_name, response = self._getResponse()
        return component_name
    
    def displayGUI(self, initialValues = ''):
        parameters = {'__NINEML_ACTION__'    : 'displayGUI',
                      '__NINEML_WEBAPP_ID__' : self.applicationID,
                      'InitialValues'        : initialValues
                     }
        self._sendRequest(parameters, self.headers)
        gui, response = self._getResponse()
        return gui
    
    def addTest(self, testName, testDescription, initialValues):
        parameters = {'__NINEML_ACTION__'    : 'addTestSkipGUI',
                      '__NINEML_WEBAPP_ID__' : self.applicationID,
                      'InitialValues'        : initialValues,
                      'testName'             : testName,
                      'testDescription'      : testDescription
                     }
        self._sendRequest(parameters, self.headers)
        validatedInitialValues, response = self._getResponse()
        return validatedInitialValues

    def generateReport(self):
        parameters = {'__NINEML_ACTION__'    : 'generateReport',
                      '__NINEML_WEBAPP_ID__' : self.applicationID
                     }
        self._sendRequest(parameters, self.headers)
        data, response = self._getResponse()
        return data

    def downloadPDF(self, **kwargs):
        def_filename     = kwargs.get('filename',         None)
        openInDefaultApp = kwargs.get('openInDefaultApp', True)
       
        parameters = {'__NINEML_ACTION__'    : 'downloadPDF',
                      '__NINEML_WEBAPP_ID__' : self.applicationID
                     }
        self._sendRequest(parameters, self.headers)
        pdf, response     = self._getResponse()
        received_filename = self._getAttachmentFilename(response)
        
        if def_filename:
            filename = def_filename
        elif received_filename:
            filename = received_filename
        else:
            RuntimeError('No filename specified')
        
        if pdf:
            f = open(filename, "w")
            f.write(pdf)
            f.close()
            if openInDefaultApp:
                if os.name == 'nt':
                    os.filestart(filename)
                elif os.name == 'posix':
                    os.system('/usr/bin/xdg-open ' + filename)  
        return pdf
        
    def downloadZIP(self, **kwargs):
        def_filename     = kwargs.get('filename',         None)
        openInDefaultApp = kwargs.get('openInDefaultApp', True)
        
        parameters = {'__NINEML_ACTION__'    : 'downloadZIP',
                      '__NINEML_WEBAPP_ID__' : self.applicationID
                     }
        self._sendRequest(parameters, self.headers)
        zip, response     = self._getResponse()
        received_filename = self._getAttachmentFilename(response)
        
        if def_filename:
            filename = def_filename
        elif received_filename:
            filename = received_filename
        else:
            RuntimeError('No filename specified')
        
        if zip:
            f = open(filename, "w")
            f.write(zip)
            f.close()
            if openInDefaultApp:
                if os.name == 'nt':
                    os.filestart(filename)
                elif os.name == 'posix':
                    os.system('/usr/bin/xdg-open ' + filename)  
        return zip

    def _getApplicationID(self):
        parameters = {'__NINEML_ACTION__' : 'getApplicationID'}
        self._sendRequest(parameters, self.headers)
        self.applicationID, response = self._getResponse()
        return self.applicationID

    def _sendRequest(self, dict_parameters, headers):
        parameters = urllib.urlencode(dict_parameters)
        self.http_connection.request('POST', '/nineml-webapp', parameters, headers)

    def _getAttachmentFilename(self, response):
        content_disposition = response.getheader('Content-Disposition', '')
        #print("content_disposition: " + content_disposition)
        
        filename = None
        if 'attachment' in content_disposition:
            regex = re.compile('attachment; filename=(\S+)')
            match = regex.match(content_disposition)
            if match:
                groups = match.groups()
                if len(groups) > 0:
                    filename = groups[0]
        return filename
        
    def _getResponse(self):
        data = None
        response = self.http_connection.getresponse()
        if(response.status != 200):
            raise RuntimeError('The http request failed: {0} {1}'.format(response.status, response.reason))
        
        content_type = response.getheader('Content-type', '')
        #print("content_type: " + content_type)
        
        if content_type == 'application/json':
            json_data = json.loads(response.read())
            if (not 'success' in json_data) or (not 'error' in json_data) or (not 'content' in json_data):
                raise RuntimeError('Invalid json response received')
            if json_data['success'] == False:
                raise RuntimeError('The error occured in NineML web application:\n' + json_data['error'])
            data = json_data['content']
        
        elif content_type == 'application/pdf':
            data = response.read()
        
        elif content_type == 'application/zip':
            data = response.read()
        
        elif content_type == 'text/html':
            data = response.read()
        
        else:
            raise RuntimeError('Unrecognized Content-type received: ' + content_type)
        
        return data, response
   
def saveFileAndOpenInDefaultApp(filename, contents):
    f = open(filename, "w")
    f.write(contents)
    f.close()
    if os.name == 'nt':
        os.filestart(filename)
    elif os.name == 'posix':
        os.system('/usr/bin/xdg-open ' + filename)  

def testTestableComponent():
    initialValues = """
{
    "timeHorizon": 1.0, 
    "reportingInterval": 0.001, 
    "initial_conditions": {
        "iaf_1coba.iaf.tspike": -10000000000, 
        "iaf_1coba.iaf.V": -0.06, 
        "iaf_1coba.cobaExcit.g": 0.0
    }, 
    "parameters": {
        "iaf_1coba.iaf.gl": 50.0, 
        "iaf_1coba.cobaExcit.vrev": 0.0, 
        "iaf_1coba.cobaExcit.q": 3.0, 
        "iaf_1coba.iaf.vreset": -0.06, 
        "iaf_1coba.cobaExcit.tau": 5.0, 
        "iaf_1coba.iaf.taurefrac": 0.008, 
        "iaf_1coba.iaf.vthresh": -0.04, 
        "iaf_1coba.iaf.vrest": -0.06, 
        "iaf_1coba.iaf.cm": 1.0
    }, 
    "variables_to_report": {
        "iaf_1coba.cobaExcit.I": true, 
        "iaf_1coba.iaf.V": true
    }, 
    "event_ports_expressions": {
        "iaf_1coba.cobaExcit.spikeinput": "0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90"
    }, 
    "active_regimes": {
        "iaf_1coba.cobaExcit": "cobadefaultregime", 
        "iaf_1coba.iaf": "subthresholdregime"
    }, 
    "analog_ports_expressions": {}
}
"""
    testName          = 'Test testable component' 
    testDescription   = 'Test Description' 
    testableComponent = 'hierachical_iaf_1coba'
    ws = nineml_web_service('localhost')
    ws.setALComponent(testableComponent)
    ws.addTest(testName, testDescription, initialValues)
    ws.generateReport()

    filename, pdf = ws.downloadPDF()
    saveFileAndOpenInDefaultApp(filename, pdf)
    filename, zip = ws.downloadZIP()
    saveFileAndOpenInDefaultApp(filename, zip)

def testUploadedComponent():
    initialValues = """
{
    "timeHorizon": 1.0, 
    "reportingInterval": 0.001, 
    "initial_conditions": {
        "iaf_1coba.iaf_tspike": -10000000000, 
        "iaf_1coba.iaf_V": -0.06, 
        "iaf_1coba.cobaExcit_g": 0.0
    }, 
    "parameters": {
        "iaf_1coba.iaf_gl": 50.0, 
        "iaf_1coba.cobaExcit_vrev": 0.0, 
        "iaf_1coba.cobaExcit_q": 3.0, 
        "iaf_1coba.iaf_vreset": -0.06, 
        "iaf_1coba.cobaExcit_tau": 5.0, 
        "iaf_1coba.iaf_taurefrac": 0.008, 
        "iaf_1coba.iaf_vthresh": -0.04, 
        "iaf_1coba.iaf_vrest": -0.06, 
        "iaf_1coba.iaf_cm": 1.0
    }, 
    "variables_to_report": {
        "iaf_1coba.cobaExcit_I": true, 
        "iaf_1coba.iaf_V": true
    }, 
    "event_ports_expressions": {
        "iaf_1coba.cobaExcit_spikeinput": "0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90"
    }, 
    "active_regimes": {
        "iaf_1coba": "Regime1"
    }, 
    "analog_ports_expressions": {
        "iaf_1coba.iaf_ISyn" : "0.0"
    }
}
"""

    testName        = 'Test uploaded component' 
    testDescription = 'Test Description' 
    xmlFile         = 'hierachical_iaf_1coba.xml'
    ws = nineml_web_service('localhost')
    ws.uploadALComponent(xmlFile)
    ws.addTest(testName, testDescription, initialValues)
    ws.generateReport()

    filename, pdf = ws.downloadPDF()
    saveFileAndOpenInDefaultApp(filename, pdf)
    filename, zip = ws.downloadZIP()
    saveFileAndOpenInDefaultApp(filename, zip)

if __name__ == "__main__":
    testTestableComponent()
    #testUploadedComponent()
    