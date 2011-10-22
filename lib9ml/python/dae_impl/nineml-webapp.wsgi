from __future__ import print_function
from pprint import pformat
import os, sys, math, json, traceback, os.path, tempfile, shutil
import cPickle as pickle
from time import localtime, strftime, time
import uuid, urlparse, zipfile, cgitb
cgitb.enable()
from ZODB.FileStorage import FileStorage
from ZODB.DB import DB
import transaction

__scriptName__ = 'nineml-webapp'
__actionName__ = '__NINEML_ACTION__'

___import_exception___ = None
___import_exception_traceback___ = None
try:
    baseFolder = '/home/ciroki/Data/NineML/nineml-model-tree/lib9ml/python/dae_impl'
    sys.path.append(baseFolder)
    os.environ['HOME'] = tempfile.gettempdir()
    #print(os.environ, file=sys.stderr)

    import nineml
    from nineml.abstraction_layer import readers
    from nineml.abstraction_layer.testing_utils import TestableComponent
    from nineml.abstraction_layer import ComponentClass

    from daetools.pyDAE import pyCore, pyActivity, pyDataReporting, pyIDAS, daeLogs
    from nineml_component_inspector import nineml_component_inspector
    from nineml_daetools_bridge import nineml_daetools_bridge
    from nineml_tex_report import createLatexReport, createPDF
    from nineml_daetools_simulation import daeSimulationInputData, nineml_daetools_simulation, ninemlTesterDataReporter
    from nineml_webapp_common import createErrorPage, getSetupDataForm, createSetupDataPage, getInitialPage, createResultPage, createDownloadResults

except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    ___import_exception___           = str(e)
    ___import_exception_traceback___ = exc_traceback

class daeNineMLWebAppLog(daeLogs.daeBaseLog):
    def __init__(self):
        daeLogs.daeBaseLog.__init__(self)

    def Message(self, message, severity):
        daeLogs.daeBaseLog.Message(self, message, severity)
        #print(self.IndentString + message, file=sys.stderr)

class nineml_webapp:
    def __init__(self):
        pass

    def initial_page(self, environ, start_response):
        available_components = sorted(TestableComponent.list_available())
        html = getInitialPage(available_components)
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]

    def log(self, function, uuid, message):
        print('{0} [{1}]:'.format(function, uuid), file=sys.stderr)
        print('  {0}'.format(message), file=sys.stderr)
    
    def error(self, e, trace_back = None):
        if not trace_back:
            trace_back = sys.exc_info()[2]
        strTraceBack = '\n'.join(traceback.format_tb(trace_back))
        results = {}
        results["success"]   = False
        results["error"]     = str(e)
        results['content']   = ''
        results['traceback'] = strTraceBack 
        html = json.dumps(results, indent = 2)

    def getAvailableALComponents(self, dictFormData, environ, start_response):
        available_components = sorted(TestableComponent.list_available())
        content = ''
        for component in available_components:
            content += '<option value="{0}">{0}</option>\n'.format(component)
        
        results = {}
        results['success'] = True
        results['error']   = ''
        results['content'] = content
        html = json.dumps(results, indent = 2)
        
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]
    
    def getApplicationID(self, dictFormData, environ, start_response):
        results = {}
        results['success'] = True
        results['error']   = ''
        results['content'] = str(uuid.uuid1())
        html = json.dumps(results, indent = 2)

        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]

    def uploadULComponent(self, dictFormData, environ, start_response):
        html = str("Success")
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]
    
    def set_AL_component(self, dictFormData, environ, start_response):
        if not dictFormData.has_key('TestableComponent'):
            raise RuntimeError('No input NineML component has been specified')

        compName = dictFormData['TestableComponent'][0]
        nineml_component = TestableComponent(compName)()
        if not nineml_component:
            raise RuntimeError('The specified component: {0} could not be loaded'.format(compName))
        
        applicationID = self.applicationIDFromDictionary(dictFormData)
        print('applicationID = ' + applicationID, file=sys.stderr)
        
        dictZODB = {}
        dictZODB['name']                = nineml_component.name
        dictZODB['nineml_component']    = nineml_component
        dictZODB['REMOTE_ADDR']         = environ['REMOTE_ADDR']
        dictZODB['HTTP_USER_AGENT']     = environ['HTTP_USER_AGENT']
        dictZODB['tests']               = {}
        
        print(dictZODB, file=sys.stderr)
        self.writeZODB(applicationID, dictZODB)
        
        print('wrote ZODB', file=sys.stderr)
    
        results = {}
        results['success'] = True
        results['error']   = ''
        results['content'] = nineml_component.name
        html = json.dumps(results, indent = 2)
        
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]
    
    def display_gui(self, dictFormData, environ, start_response):
        html = ''
        content = ''
        raw_arguments = ''
        timeHorizon = 0.0
        reportingInterval = 0.0
        parameters = {}
        initial_conditions = {}
        analog_ports_expressions = {}
        event_ports_expressions = {}
        active_regimes = {}
        variables_to_report = {}

        applicationID = self.applicationIDFromDictionary(dictFormData)
        print('applicationID = ' + applicationID, file=sys.stderr)
        
        data = {}
        if dictFormData.has_key('InitialValues'):
            try:
                data = json.loads(dictFormData['InitialValues'][0])
            except Exception as e:
                pass

        simulation_data = daeSimulationInputData()
        simulation_data.loadDictionary(data)
        
        dictZODB = self.readZODB(applicationID)
        if not dictZODB:
            raise RuntimeError('Invalid application ID has been specified') 
        
        nineml_component = dictZODB['nineml_component']
        
        inspector = nineml_component_inspector()
        inspector.inspect(nineml_component, timeHorizon              = simulation_data.timeHorizon,
                                            reportingInterval        = simulation_data.reportingInterval,
                                            parameters               = simulation_data.parameters,
                                            initial_conditions       = simulation_data.initial_conditions,
                                            active_regimes           = simulation_data.active_regimes,
                                            analog_ports_expressions = simulation_data.analog_ports_expressions,
                                            event_ports_expressions  = simulation_data.event_ports_expressions,
                                            variables_to_report      = simulation_data.variables_to_report)

        results = {}
        results['success'] = True
        results['error']   = ''
        results['content'] = inspector.generateHTMLForm()
        html = json.dumps(results, indent = 2)
        
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]

    def add_test(self, dictFormData, environ, start_response):
        applicationID = self.applicationIDFromDictionary(dictFormData)

        dictZODB = self.readZODB(applicationID)
        if not dictZODB:
            raise RuntimeError('Invalid application ID has been specified') 
        
        testName, testDescription, simulation_data = self.getSimulationData(dictFormData)
        print("add_test:", file=sys.stderr)
        print(simulation_data, file=sys.stderr)
        
        tests = dictZODB['tests'];
        tests[testName] = (testDescription, simulation_data)          
        dictZODB['tests'] = tests;
        self.writeZODB(applicationID, dictZODB)
        
        results = {}
        results['success'] = True
        results['error']   = ''
        results['content'] = simulation_data.asJSON()
        html = json.dumps(results, indent = 2)
            
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]

    def getSimulationData(self, dictFormData):
        testName = ''
        testDescription = ''
        timeHorizon = 0.0
        reportingInterval = 0.0
        parameters = {}
        initial_conditions = {}
        analog_ports_expressions = {}
        event_ports_expressions = {}
        active_regimes = {}
        variables_to_report = {}
        
        if dictFormData.has_key('testName'):
            testName = str(dictFormData['testName'][0])
        if dictFormData.has_key('testDescription'):
            testDescription = str(dictFormData['testDescription'][0])
        if dictFormData.has_key('timeHorizon'):
            timeHorizon = float(dictFormData['timeHorizon'][0])
        if dictFormData.has_key('reportingInterval'):
            reportingInterval = float(dictFormData['reportingInterval'][0])

        for key, values in dictFormData.items():
            names = key.split('.')
            if len(names) > 0:
                canonicalName = '.'.join(names[1:])

                if names[0] == nineml_component_inspector.categoryParameters:
                    parameters[canonicalName] = float(values[0])

                elif names[0] == nineml_component_inspector.categoryInitialConditions:
                    initial_conditions[canonicalName] = float(values[0])

                elif names[0] == nineml_component_inspector.categoryActiveStates:
                    active_regimes[canonicalName] = values[0]

                elif names[0] == nineml_component_inspector.categoryAnalogPortsExpressions:
                    analog_ports_expressions[canonicalName] = values[0]

                elif names[0] == nineml_component_inspector.categoryEventPortsExpressions:
                    event_ports_expressions[canonicalName] = values[0]

                elif names[0] == nineml_component_inspector.categoryVariablesToReport:
                    if values[0] == 'on':
                        variables_to_report[canonicalName] = True

        simulation_data = daeSimulationInputData()
        simulation_data.timeHorizon              = timeHorizon
        simulation_data.reportingInterval        = reportingInterval
        simulation_data.parameters               = parameters
        simulation_data.initial_conditions       = initial_conditions
        simulation_data.analog_ports_expressions = analog_ports_expressions
        simulation_data.event_ports_expressions  = event_ports_expressions
        simulation_data.active_regimes           = active_regimes
        simulation_data.variables_to_report      = variables_to_report
        
        return testName, testDescription, simulation_data
        
    def generate_report(self, dictFormData, environ, start_response):
        results = {}
        results['success'] = True
        results['error']   = ''
        results['content'] = str(dictFormData)
        html = json.dumps(results, indent = 2)
        
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]
        
    def generate_report_with_no_tests(self, dictFormData, environ, start_response):
        try:
            if not dictFormData.has_key('TestableComponent'):
                raise RuntimeError('No input NineML component has been specified')

            compName = dictFormData['TestableComponent'][0]
            nineml_component = TestableComponent(compName)()
            if not nineml_component:
                raise RuntimeError('The specified component: {0} could not be loaded'.format(compName))

            inspector = nineml_component_inspector()
            inspector.inspect(nineml_component)
            applicationID = self.generate_applicationID()

            dictZODB = {}
            dictZODB['inspector']           = inspector
            #dictZODB['nineml_component']    = nineml_component
            dictZODB['REMOTE_ADDR']         = environ['REMOTE_ADDR']
            dictZODB['HTTP_USER_AGENT']     = environ['HTTP_USER_AGENT']
            dictZODB['name']                = nineml_component.name
            
            applicationID = self.generate_applicationID()
            self.writeZODB(applicationID, dictZODB)
            
            return self.generate_report(dictFormData, applicationID, inspector, nineml_component, False, environ, start_response)
        
        except Exception as e:
            return self.returnExceptionPage(str(e), dictFormData, environ, start_response)

    def generate_report_with_tests(self, dictFormData, environ, start_response):
        try:
            applicationID = self.applicationIDFromDictionary(dictFormData)
            dictZODB = self.readZODB(applicationID)
            if not dictZODB:
                raise RuntimeError('Invalid application ID has been specified') 
            
            inspector        = dictZODB['inspector']
            nineml_component = inspector.ninemlComponent #dictZODB['nineml_component']
            
            return self.generate_report(dictFormData, applicationID, inspector, nineml_component, True, environ, start_response)
       
        except Exception as e:
            return self.returnExceptionPage(str(e), dictFormData, environ, start_response)
    
    def readZODB(self, key):
        try:
            _storage_    = FileStorage(baseFolder + '/zodb/nineml-webapp.zodb')
            _db_         = DB(_storage_)
            _connection_ = _db_.open()
            _root_       = _connection_.root()
        
            if not key in _root_:
                raise RuntimeError('Cannot read key: {0} from database'.format(key))
            return _root_[key]
        
        finally:
            transaction.abort()
            _connection_.close()
            _db_.close()
            _storage_.close()
        
    def writeZODB(self, key, data):
        try:
            _storage_    = FileStorage(baseFolder + '/zodb/nineml-webapp.zodb')
            _db_         = DB(_storage_)
            _connection_ = _db_.open()
            _root_       = _connection_.root()
            
            _root_[key] = data
            transaction.commit()
        
        except Exception as e:
            print(str(e), file=sys.stderr)

        finally:
            transaction.abort()
            _connection_.close()
            _db_.close()
            _storage_.close()
    
    def generate_report(self, dictFormData, applicationID, inspector, nineml_component, doTests, environ, start_response):
        try:
            pdf = None
            zip = None
            html = ''
            html_tests = ''
            texReport = ''
            pdfReport = ''
            zipReport = ''
            tests_data = []
            
            success = False
            tmpFolder = self.create_temp_folder()
            
            if doTests:
                html_tests, tests_data, zip = self.do_tests(nineml_component, applicationID, tmpFolder, dictFormData)
                
            texReport = '{0}/{1}.tex'.format(tmpFolder, applicationID)
            pdfReport = '{0}/{1}.pdf'.format(tmpFolder, applicationID)

            # Copy the logo image to tmp folder
            shutil.copy2(os.path.join(baseFolder, 'logo.png'), 
                         os.path.join(tmpFolder, 'logo.png'))
            # Generate Tex report
            createLatexReport(inspector, tests_data, os.path.join(baseFolder, 'nineml-tex-template.tex'), texReport, tmpFolder)

            # Generate PDF report
            createPDF = os.path.join(tmpFolder, 'createPDF.sh')
            createPDFfile = open(createPDF, "w")
            createPDFfile.write('cd {0}\n'.format(tmpFolder))
            # Run it twice because of the problems with the Table Of Contents (we need two passes)
            createPDFfile.write('/usr/bin/pdflatex -interaction=nonstopmode {0}\n'.format(texReport))
            createPDFfile.write('/usr/bin/pdflatex -interaction=nonstopmode {0}\n'.format(texReport))
            createPDFfile.close()
            os.system('sh {0}'.format(createPDF))

            # Read the contents of the report into a variable (to be sent together with the .html part)
            if os.path.isfile(pdfReport):
                pdf = open(pdfReport, "rb").read()
            
            dictZODB = self.readZODB(applicationID)
            dictZODB['pdfReport']   = pdf
            dictZODB['zipReport']   = zip
            dictZODB['tests_data']  = tests_data
            
            self.writeZODB(applicationID, dictZODB)
            
            success = True
            html = html_tests

        except Exception as e:
            return self.returnExceptionPage(str(e), dictFormData, environ, start_response)
        
        finally:
            # Remove temporary directory
            if os.path.isdir(tmpFolder):
                shutil.rmtree(tmpFolder)
            
        if success:
            enablePDF = False
            enableZIP = False
            if pdf:
                enablePDF = True
            if zip:
                enableZIP = True
            output = createDownloadResults(html, applicationID, enablePDF, enableZIP)
            output_len = len(output)
            start_response('200 OK', [('Content-type', 'text/html'),
                                      ('Content-Length', str(output_len))])
            return [output]
        else:
            output_len = len(html)
            start_response('200 OK', [('Content-type', 'text/html'),
                                      ('Content-Length', str(output_len))])
            return [html]

    def downloadPDF(self, dictFormData, environ, start_response):
        applicationID = self.applicationIDFromDictionary(dictFormData)
        dictZODB = self.readZODB(applicationID)
        pdf  = dictZODB['pdfReport']
        name = dictZODB['name']
        html = str(pdf)        
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'application/pdf'),
                                  #('Content-Transfer-Encoding', 'base64'),
                                  ('Content-Disposition', 'attachment; filename={0}.pdf'.format(name)),
                                  ('Content-Length', str(output_len))])
        return [html]
    
    def downloadZIP(self, dictFormData, environ, start_response):
        applicationID = self.applicationIDFromDictionary(dictFormData)
        dictZODB = self.readZODB(applicationID)
        zip  = dictZODB['zipReport']
        name = dictZODB['name']
        html = str(zip)        
        output_len = len(html)
        start_response('200 OK', [('Content-type', 'application/zip'),
                                  #('Content-Transfer-Encoding', 'base64'),
                                  ('Content-Disposition', 'attachment; filename={0}.zip'.format(name)),
                                  ('Content-Length', str(output_len))])
        return [html]
    
    def do_tests(self, nineml_component, applicationID, tmpFolder, dictFormData):
        tests_data = []
        html       = ''
        zip        = None
        
        isOK, results = self.run_test(nineml_component, dictFormData, tmpFolder)
        
        if isOK:
            testName, testDescription, dictInputs, plots, log_output = results
            tests_data.append( (testName, testDescription, dictInputs, plots, log_output, tmpFolder) )
            zipReport = '{0}/{1}.zip'.format(tmpFolder, applicationID)
            self.pack_tests_data(zipReport, tests_data)
            html += 'Test status: {0} [SUCCEEDED]'.format(testName)
            if os.path.isfile(zipReport):
                zip = open(zipReport, "rb").read()
        else:
            testName, testDescription, dictInputs, plots, log_output, error = results
            html += 'Test status: {0} [FAILED]\n'.format(testName)
            html += error
        
        return html, tests_data, zip

    def returnExceptionPage(self, strError, dictFormData, environ, start_response):
        content = 'Form arguments:\n  {0}\n\n'.format(dictFormData)

        exc_traceback = sys.exc_info()[2]
        html = createErrorPage(strError, exc_traceback, content)

        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]
    
    def applicationIDFromDictionary(self, dictFormData):
        if not dictFormData.has_key('__NINEML_WEBAPP_ID__'):
            raise RuntimeError('No application ID has been specified')

        applicationID   = dictFormData['__NINEML_WEBAPP_ID__'][0]
        if applicationID == '':
            raise RuntimeError('No application ID has been specified')
        return applicationID
        
    def generate_applicationID(self):
        return str(uuid.uuid1())
    
    def create_temp_folder(self):
        tmpFolder = tempfile.mkdtemp(prefix='nineml-webapp-')
        os.chmod(tmpFolder, 0777)
        return tmpFolder

    def pack_tests_data(self, zipReport, tests_data):
        try:
            if len(tests_data) == 0:
                return
                
            zip = zipfile.ZipFile(zipReport, "w")
            
            for i, test_data in enumerate(tests_data):
                testName, testDescription, dictInputs, plots, log_output, tmpFolder = test_data
                testFolder = 'test-no.{0}/'.format(i+1, testName) 
                
                # Write log file contents
                logName = '__log_output__.txt'
                f = open(tmpFolder + '/' + logName, "w")
                f.write(log_output)
                f.close()
                zip.write(tmpFolder + '/' + logName, testFolder + logName)

                # Write JSON input file
                jsonName = '__json_simulation_input__.txt'
                f = open(tmpFolder + '/' + jsonName, "w")
                json.dump(dictInputs, f, indent = 2)
                f.close()
                zip.write(tmpFolder + '/' + jsonName, testFolder + jsonName)

                # Write .png and .csv files
                for plot in plots:
                    varName, xPoints, yPoints, pngName, csvName = plot
                    zip.write(tmpFolder + '/' + pngName, testFolder + pngName)
                    zip.write(tmpFolder + '/' + csvName, testFolder + csvName)
            
            zip.close()
            
        except Exception as e:
            exc_traceback = sys.exc_info()[2]
            print(str(e), '\n'.join(traceback.format_tb(exc_traceback)), file=sys.stderr)
    
    def run_test(self, nineml_component, dictFormData, tmpFolder):
        try:
            testName = 'Test name'
            testDescription = 'Test description'
            timeHorizon = 0.0
            reportingInterval = 0.0
            parameters = {}
            initial_conditions = {}
            analog_ports_expressions = {}
            event_ports_expressions = {}
            active_regimes = {}
            variables_to_report = {}
            log_output = ''
            log          = None
            daesolver    = None
            datareporter = None
            model        = None
            simulation   = None
            dictInputs = {}

            if dictFormData.has_key('testName'):
                testName = str(dictFormData['testName'][0])
            if dictFormData.has_key('testDescription'):
                testDescription = str(dictFormData['testDescription'][0])
            if dictFormData.has_key('timeHorizon'):
                timeHorizon = float(dictFormData['timeHorizon'][0])
            if dictFormData.has_key('reportingInterval'):
                reportingInterval = float(dictFormData['reportingInterval'][0])

            for key, values in dictFormData.items():
                names = key.split('.')
                if len(names) > 0:
                    canonicalName = '.'.join(names[1:])

                    if names[0] == nineml_component_inspector.categoryParameters:
                        parameters[canonicalName] = float(values[0])

                    elif names[0] == nineml_component_inspector.categoryInitialConditions:
                        initial_conditions[canonicalName] = float(values[0])

                    elif names[0] == nineml_component_inspector.categoryActiveStates:
                        active_regimes[canonicalName] = values[0]

                    elif names[0] == nineml_component_inspector.categoryAnalogPortsExpressions:
                        analog_ports_expressions[canonicalName] = values[0]

                    elif names[0] == nineml_component_inspector.categoryEventPortsExpressions:
                        event_ports_expressions[canonicalName] = values[0]

                    elif names[0] == nineml_component_inspector.categoryVariablesToReport:
                        if values[0] == 'on':
                            variables_to_report[canonicalName] = True

            simulation_data = daeSimulationInputData()
            simulation_data.timeHorizon              = timeHorizon
            simulation_data.reportingInterval        = reportingInterval
            simulation_data.parameters               = parameters
            simulation_data.initial_conditions       = initial_conditions
            simulation_data.analog_ports_expressions = analog_ports_expressions
            simulation_data.event_ports_expressions  = event_ports_expressions
            simulation_data.active_regimes           = active_regimes
            simulation_data.variables_to_report      = variables_to_report

            # Create Log, DAESolver, DataReporter and Simulation object
            log          = daeNineMLWebAppLog()
            daesolver    = pyIDAS.daeIDAS()
            datareporter = ninemlTesterDataReporter()
            model        = nineml_daetools_bridge(nineml_component.name, nineml_component)
            simulation   = nineml_daetools_simulation(model, timeHorizon              = timeHorizon,
                                                             reportingInterval        = reportingInterval,
                                                             parameters               = simulation_data.parameters,
                                                             initial_conditions       = simulation_data.initial_conditions,
                                                             active_regimes           = simulation_data.active_regimes,
                                                             analog_ports_expressions = simulation_data.analog_ports_expressions,
                                                             event_ports_expressions  = simulation_data.event_ports_expressions,
                                                             variables_to_report      = simulation_data.variables_to_report)

            # Set the time horizon and the reporting interval
            simulation.ReportingInterval = simulation_data.reportingInterval
            simulation.TimeHorizon       = simulation_data.timeHorizon

            # Connect data reporter
            simName = simulation.m.Name + strftime(" [%d.%m.%Y %H:%M:%S]", localtime())
            if(datareporter.Connect("", simName) == False):
                raise RuntimeError('Cannot connect a TCP/IP datareporter; did you forget to start daePlotter?')

            # Initialize the simulation
            simulation.Initialize(daesolver, datareporter, log)

            # Save the model reports for all models
            #simulation.m.SaveModelReport(simulation.m.Name + ".xml")
            #simulation.m.SaveRuntimeModelReport(simulation.m.Name + "-rt.xml")

            # Solve at time=0 (initialization)
            simulation.SolveInitial()

            # Run
            simulation.Run()
            simulation.Finalize()

            log_output = log.JoinMessages('\n')
            
            dictInputs['parameters']                = parameters
            dictInputs['initial_conditions']        = initial_conditions
            dictInputs['analog_ports_expressions']  = analog_ports_expressions
            dictInputs['event_ports_expressions']   = event_ports_expressions
            dictInputs['active_regimes']            = active_regimes
            dictInputs['variables_to_report']       = variables_to_report
            dictInputs['timeHorizon']               = timeHorizon
            dictInputs['reportingInterval']         = reportingInterval
            plots = datareporter.createReportData(tmpFolder)

            return True, (testName, testDescription, dictInputs, plots, log_output)
            
        except Exception as e:
            if log:
                log_output = '<pre>{0}</pre>'.format(log.JoinMessages('\n'))
            return False, (testName, testDescription, dictInputs, None, log_output, str(e))
        
    def __call__(self, environ, start_response):
        try:
            html = ''
            if not ___import_exception___:
                if environ['REQUEST_METHOD'] == 'GET':
                    return self.initial_page(environ, start_response)

                else:
                    content_length = int(environ['CONTENT_LENGTH'])
                    raw_arguments = pformat(environ['wsgi.input'].read(content_length))
                    raw_arguments = raw_arguments.strip(' \'')
                    dictFormData  = urlparse.parse_qs(raw_arguments)

                    if not __actionName__ in dictFormData:
                        raise RuntimeError('Phase argument must be specified')

                    action = dictFormData[__actionName__][0]
                    
                    if action == 'getAvailableALComponents':
                        return self.getAvailableALComponents(dictFormData, environ, start_response)
                        
                    elif action == 'getApplicationID':
                        return self.getApplicationID(dictFormData, environ, start_response)
                    
                    elif action == 'uploadULComponent':
                        return self.uploadULComponent(dictFormData, environ, start_response)
                    
                    elif action == 'setALComponent':
                        return self.set_AL_component(dictFormData, environ, start_response)
                    
                    elif action == 'displayGUI':
                        return self.display_gui(dictFormData, environ, start_response)
                    
                    elif action == 'addTest':
                        return self.add_test(dictFormData, environ, start_response)
                    
                    elif action == 'generateReport':
                        return self.generate_report(dictFormData, environ, start_response)
                        #return self.generate_report_with_no_tests(dictFormData, environ, start_response)

                    elif action == 'Generate report with tests':
                        return self.generate_report_with_tests(dictFormData, environ, start_response)
                    
                    elif action == 'Download pdf report':
                        return self.downloadPDF(dictFormData, environ, start_response)
                    
                    elif action == 'Download zip archive':
                        return self.downloadZIP(dictFormData, environ, start_response)
                    
                    else:
                        raise RuntimeError('Invalid action argument specified: {0}'.format(action))
            else:
                html = self.error(___import_exception___, ___import_exception_traceback___)

        except Exception as e:
            html = self.error(e)

        output_len = len(html)
        start_response('200 OK', [('Content-type', 'text/html'),
                                  ('Content-Length', str(output_len))])
        return [html]

application = nineml_webapp()