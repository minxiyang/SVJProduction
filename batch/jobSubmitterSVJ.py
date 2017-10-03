from Condor.Production.jobSubmitter import *
from SVJ.Production.svjHelper import svjHelper

class jobSubmitterSVJ(jobSubmitter):
    def __init__(self):
        super(jobSubmitterSVJ,self).__init__()
        
        self.helper = svjHelper()

    def addDefaultOptions(self,parser):
        super(jobSubmitterSVJ,self).addDefaultOptions(parser)
        parser.add_option("-g", "--getpy", dest="getpy", default=False, action="store_true", help="make python file list for ntuple production (default = %default)")

    def addExtraOptions(self,parser):
        super(jobSubmitterSVJ,self).addExtraOptions(parser)
        
        parser.add_option("-d", "--dicts", dest="dicts", default="", help="file with list of input dicts; each dict contains signal parameters (required) (default = %default)")
        parser.add_option("-o", "--output", dest="output", default="", help="path to output directory in which root files will be stored (required) (default = %default)")
        parser.add_option("-E", "--maxEvents", dest="maxEvents", default=1, help="number of events to process per job (default = %default)")
        parser.add_option("-F", "--firstPart", dest="firstPart", default=1, help="first part to process, in case extending a sample (default = %default)")
        parser.add_option("-N", "--nParts", dest="nParts", default=1, help="number of parts to process (default = %default)")
        parser.add_option("--indir", dest="indir", default="", help="input file directory (LFN) (default = %default)")
        parser.add_option("--redir", dest="redir", default="root://cmseos.fnal.gov/", help="input file redirector (default = %default)")
        parser.add_option("--inpre", dest="inpre", default="", help="input file prefix (default = %default)")
        parser.add_option("--outpre", dest="outpre", default="", help="output file prefix (required) (default = %default)")
        parser.add_option("--config", dest="config", default="", help="CMSSW config to run (required) (default = %default)")
        parser.add_option("-A", "--args", dest="args", default="", help="additional common args to use for all jobs (default = %default)")
        parser.add_option("-v", "--verbose", dest="verbose", default=False, action="store_true", help="enable verbose output (default = %default)")

    def run(self):
        super(jobSubmitterSVJ,self).run()
        if self.getpy:
            self.finishPy()
        
    def checkDefaultOptions(self,options,parser):
        if (options.submit + options.count + options.missing)>1:
            parser.error("Options -c, -s, -m are exclusive, pick one!")
        if (options.submit + options.count + options.missing + options.prepare + options.getpy)==0:
            parser.error("No operation mode selected! (-c, -p, -s, -m, -g)")

    def checkExtraOptions(self,options,parser):
        super(jobSubmitterSVJ,self).checkExtraOptions(options,parser)
    
        if options.dicts is None or len(options.dicts)==0:
            parser.error("Required option: --dicts [dict]")
            
        if options.prepare or not options.count:
            if len(options.output)==0:
                parser.error("Required option: --output [directory]")
            if len(options.outpre)==0:
                parser.error("Required option: --outpre [str]")
            if len(options.config)==0:
                parser.error("Required option: --config [str]")
            
    def generateExtra(self,job):
        super(jobSubmitterSVJ,self).generateExtra(job)
        job.patterns.update([
            ("JOBNAME",job.name+"_part-$(Process)_$(Cluster)"),
            ("EXTRAINPUTS","input/args_"+job.name+".txt"),
            ("EXTRAARGS","-j "+job.name+" -p $(Process) -o "+self.output),
        ])
        if "cmslpc" in os.uname()[1]:
            job.appends.append(
                'ONE_DAY = 86400\n'
                'periodic_hold = (\\\n'
                '    ( JobUniverse == 5 && JobStatus == 2 && CurrentTime - EnteredCurrentStatus > $(ONE_DAY) * 1.75 ) || \\\n'
                '    ( JobRunCount > 8 ) || \\\n'
                '    ( JobStatus == 5 && CurrentTime - EnteredCurrentStatus > $(ONE_DAY) * 6 ) || \\\n'
                '    ( DiskUsage > 38000000 ) || \\\n'
                '    ( ResidentSetSize > RequestMemory * 950 ) )\n'
                'periodic_hold_reason = strcat("Job held by PERIODIC_HOLD due to ", \\\n'
                '    ifThenElse(( JobUniverse == 5 && JobStatus == 2 && CurrentTime - EnteredCurrentStatus > $(ONE_DAY) * 1.75 ), "runtime longer than 1.75 days", \\\n'
                '    ifThenElse(( JobRunCount > 8 ), "JobRunCount greater than 8", \\\n'
                '    ifThenElse(( JobStatus == 5 && CurrentTime - EnteredCurrentStatus > $(ONE_DAY) * 6 ), "hold time longer than 6 days", \\\n'
                '    ifThenElse(( DiskUsage > 38000000 ), "disk usage greater than 38GB", \\\n'
                '                strcat("memory usage ",ResidentSetSize," greater than requested ",RequestMemory*1000))))), ".")'
            )
        
    def generateSubmission(self):
        # get dicts
        flist = __import__(self.dicts.replace(".py","")).flist
        # loop over dicts
        for pdict in flist:
            # create protojob
            job = protoJob()
            # make name from params
            job.name = self.helper.getOutName(pdict["mZprime"],pdict["mDark"],pdict["rinv"],pdict["alpha"],int(self.maxEvents),outpre=self.outpre)
            if self.verbose:
                print "Creating job: "+job.name
            self.generatePerJob(job)
            
            # write job options to file - will be transferred with job
            if self.prepare:
                with open("input/args_"+job.name+".txt",'w') as argfile:
                    arglist = [
                        "mZprime="+str(pdict["mZprime"]),
                        "mDark="+str(pdict["mDark"]),
                        "rinv="+str(pdict["rinv"]),
                        "alpha="+str(pdict["alpha"]),
                        "maxEvents="+str(self.maxEvents),
                        "outpre="+self.outpre,
                        "config="+self.config,
                    ]
                    if len(self.indir)>0:
                        arglist.append("indir="+self.indir)
                    if len(self.inpre)>0:
                        arglist.append("inpre="+self.inpre)
                    if len(self.args)>0:
                        arglist.insert(0,self.args)
                    if self.cpus>1:
                        arglist.append("threads="+str(self.cpus))
                    if len(self.redir)>1:
                        arglist.append("redir="+self.redir)
                    argfile.write(" ".join(arglist))
            
            # start loop over N jobs
            for iJob in xrange(int(self.nParts)):
                # get real part number
                iActualJob = iJob+self.firstPart
                
                job.njobs += 1
                if self.count and not self.prepare:
                    continue

                job.nums.append(str(iActualJob))
                job.names.append(job.name+"_part-"+str(iActualJob))
            
            # append queue comment
            job.queue = "-queue Process in "+','.join(job.nums)
            
            # store protojob
            self.protoJobs.append(job)

    def makeResubmit(self,diffList):
        with open(self.resub,'w') as rfile:
            rfile.write("#!/bin/bash\n\n")
            diffDict = defaultdict(list)
            for dtmp in diffList:
                stmp = self.jobRef[dtmp].jdl
                ntmp = dtmp.split('_')[-1].split('-')[-1]
                diffDict[stmp].append(ntmp)
            for stmp in sorted(diffDict):
                rfile.write('condor_submit '+stmp+' -queue Process in '+','.join(diffDict[stmp])+'\n')
        # make executable
        st = os.stat(rfile.name)
        os.chmod(rfile.name, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def finishPy(self):
        for job in self.protoJobs:
            with open(job.name+"_cff.py",'w') as outfile:
                outfile.write("import FWCore.ParameterSet.Config as cms\n\n")
                outfile.write("maxEvents = cms.untracked.PSet( input = cms.untracked.int32(-1) )\n")
                outfile.write("readFiles = cms.untracked.vstring()\n")
                outfile.write("secFiles = cms.untracked.vstring()\n")
                outfile.write("source = cms.Source (\"PoolSource\",fileNames = readFiles, secondaryFileNames = secFiles)\n")
                counter = 0
                #split into chunks of 255
                for ijob in job.names:
                    if counter==0: outfile.write("readFiles.extend( [\n")
                    outfile.write("       '"+self.indir+"/"+ijob+".root',\n")
                    if counter==254 or ijob==job.names[-1]:
                        outfile.write("] )\n")
                        counter = 0
                    else:
                        counter += 1

