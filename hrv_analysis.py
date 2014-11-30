####
# code to calculate HRV descriptors
#
# based on  gHRV: a graphical application for Heart Rate Variability analysis, Copyright (C) 2013  Milegroup - Dpt. Informatics, University of Vigo - Spain, www.milegroup.net
# Authors: Leandro Rodríguez-Liñares, Arturo Méndez, María José Lado, Xosé Antón Vila
#
# adapted by A. Riss, 2014
#
####

# ranges for 
CFG_vlfmin = 0.0033   # very low frequency
CFG_vlfmax = 0.04

CFG_lfmin = 0.04   # low frequency
CFG_lfmax = 0.15

CFG_hfmin = 0.15   # high frequency
CFG_hfmax = 0.40

CFG_interpolate_freq = 4  # Hz
    
    
from scipy import interpolate
import numpy as np


class HRVdescriptors():
    def power(self,spec,freq,fmin,fmax):
        band = [spec[i] for i in range(len(spec)) if freq[i] >= fmin and freq[i]<fmax]
        powerinband = np.sum(band)/(2*len(spec)**2)
        return powerinband

    def calculate(self, IBI):
        """ calculates HRV descriptors from an array of inter-beat-intervals (in ms)
        returns a dictionary with:
            VLF:    power of very low frequency components
            LF:     power of low frequency components
            HF:     power of high frequency components
            LFHF:   ratio of LF to HF
            Power:  total power
            HRMean: heart rate mean
            HRSTD:  heart rate standard devaiation
            pNN50
            rMSSD
            ApEn
            FracDim
        """
        
        #signal=1000/(self.data["HR"]/60.0) # msec.   / old code, left if we need to check later / Alex
        
        if len(IBI)<2: return False
        
        result = {}
        
        time_axis = np.cumsum(IBI)-IBI[0]  # time in ms, starts at 0
        HR = 60.0 / (IBI / 1000)
        
        step=1.0/CFG_interpolate_freq
        time_axis_interp = np.arange(time_axis[0],time_axis[-1],step)

        interp_IBI = interpolate.interp1d(time_axis, IBI)
        interp_HR = interpolate.interp1d(time_axis, HR)
        IBI_interp = interp_IBI(time_axis_interp)
        HR_interp = interp_HR(time_axis_interp)

        spec_tmp = np.absolute(np.fft.fft(IBI_interp))**2
        spec = spec_tmp[0:(len(spec_tmp)/2)] # Only positive half of spectrum

        freqs = np.linspace(start=0,stop=CFG_interpolate_freq/2,num=len(spec),endpoint=True)

        result['VLF'] = self.power(spec,freqs,CFG_vlfmin,CFG_vlfmax)
        result['LF'] = self.power(spec,freqs,CFG_lfmin,CFG_lfmax)
        result['HF'] = self.power(spec,freqs,CFG_hfmin,CFG_hfmax)
        result['Power'] = self.power(spec,freqs,0,CFG_interpolate_freq/2.0)

        #print("ULF+VLF+LF+HF power: "+str(ulfpower+vlfpower+lfpower+hfpower))
        result['LFHF'] = result['LF']/result['HF']
            
        result['HRMean'] = np.mean(HR)
        result['HRSTD'] = np.std(HR,ddof=1)
            
        #BeatsFrame = [x for x in self.data["BeatTime"] if x>=begtime and x<=endtime]
        #frameRR = 1000.0*np.diff(BeatsFrame)   # that is our IBI  / Alex
            
        RRDiffs = np.diff(IBI)
        RRDiffs50 = [x for x in np.abs(RRDiffs) if x>50]
        result["pNN50"] = 100.0*len(RRDiffs50)/len(RRDiffs)
        result["rMSSD"] = np.sqrt(np.mean(RRDiffs**2))

        if False:  # non-linear stuff does not work yet, let's deal with it later / Alex
            BeatsFrame = time_axis / 1000  # I think that should be the BeatsFrane / Alex
            ApEn, FracDim = self.CalculateNonLinearAnalysis(BeatsFrame)
            result["ApEn"] = ApEn
            result["FracDim"] = FracDim
        return result
        
        
    def CalculateNonLinearAnalysis(self,Data=None, N=1000):

        def BuildTakensVector(Data,m,tau):
            # DataInt = range(1001)
            N = len(Data)
            jump = tau
            maxjump=(m-1)*jump
            jumpsvect=range(0,maxjump+1,jump)
            # print("jumpsvect: "+str(jumpsvect))
            numjumps=len(jumpsvect)
            numelem=N-maxjump
            # print("Building matrix "+str(numelem)+"x"+str(numjumps))
            DataExp = np.zeros(shape=(numelem,numjumps))
            for i in range(numelem):
                for j in range(numjumps):
                    DataExp[i,j]=Data[jumpsvect[j]+i]

            # print("DataExp first row: "+str(DataExp[0]))
            # print("DataExp last row: "+str(DataExp[-1]))

            return DataExp
            # --------------------


        def AvgIntegralCorrelation(Data,m,tau,r):

            from scipy.spatial.distance import cdist

            DataExp = BuildTakensVector(Data, m, tau)
            numelem=DataExp.shape[0]
            # print("Number of rows: "+str(numelem))
            mutualDistance=cdist(DataExp,DataExp,'chebyshev')

            Cmr=np.zeros(numelem)

            for i in range(numelem):
                vector=mutualDistance[i]
                Cmr[i]=float((vector <=r).sum())/numelem

            print(Cmr)
            Phi=(np.log(Cmr)).sum()/len(Cmr)

            # if self.data["Verbose"]:
            #     print("      m="+str(m))
            #     print("      Integral correlation: "+str(Cmr.sum()))
            #     print("      Average integral correlation: "+str(Phi))

            return Phi



        def CalculateApEn(Data,m=2,tau=1,r=0.2):

            r=r*np.std(Data,ddof=1)
            # print("r: "+str(r))
            Phi1 = AvgIntegralCorrelation(Data,m,tau,r)
            Phi2 = AvgIntegralCorrelation(Data,m+1,tau,r)
            
            return Phi1-Phi2


        def CalculateFracDim(Data, m=10, tau=3, Cra=0.005, Crb=0.75):

            from scipy.spatial.distance import pdist
            from scipy.stats.mstats import mquantiles

            DataExp=BuildTakensVector(Data,m,tau)
            # print("Number of rows: "+str(DataExp.shape[0]))
            # print("Number of columns: "+str(DataExp.shape[1]))

            mutualDistance=pdist(DataExp,'chebyshev')

            numelem=len(mutualDistance)
            # print("numelem: "+str(numelem))
            
            rr=mquantiles(mutualDistance,prob=[Cra,Crb])
            ra=rr[0]
            rb=rr[1]

            Cmra= float(((mutualDistance <= ra).sum()))/numelem
            Cmrb= float(((mutualDistance <= rb).sum()))/numelem

            # if self.data["Verbose"]:
            #     print("      ra: "+str(ra))
            #     print("      rb: "+str(rb))
            #     print("      Cmra: "+str(100.0*Cmra)+"%")
            #     print("      Cmrb: "+str(100.0*Cmrb)+"%")

            FracDim = (np.log(Cmrb)-np.log(Cmra))/(np.log(rb)-np.log(ra))

            return FracDim
            # --------------------


        # if self.data["Verbose"]:
        #     print("** Calculating non-linear parameters")

        npoints=len(Data)

        # print ("Number of points: "+str(npoints))
        if npoints > N:
            DataInt=Data[(npoints/2-N/2)-1:(npoints/2+N/2)]
        else:
            DataInt=Data

        # dd=np.linspace(start=0, stop=100, num=1000)
        # DataInt=np.sin(dd)

        # if self.data["Verbose"]:
        #     print("   Calculating approximate entropy")
        ApEn = CalculateApEn(DataInt)

        # if self.data["Verbose"]:
        #     print("   Approximate entropy: "+str(ApEn))

        # if self.data["Verbose"]:
        #     print("   Calculating fractal dimension")
        FracDim = CalculateFracDim(DataInt)
        # if self.data["Verbose"]:
        #     print("  Fractal dimension: "+str(FracDim))

        return ApEn,FracDim
        
                        