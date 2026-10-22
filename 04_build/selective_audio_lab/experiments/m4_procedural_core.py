"""Original HESYCHIA synthetic signal helpers, extracted from prior stress experiment.
Not real audio; not a general-purpose speech separator or event classifier.
"""
from __future__ import annotations
import os
os.environ['KERAS_BACKEND'] = 'torch'
import keras
import numpy as np
from scipy import signal
SR=16000
N_FFT=512
HOP=160
FRAMES=32
BINS=N_FFT//2+1
SAMPLES=(FRAMES-1)*HOP
TARGET_CLASS=8
EPS=1e-9
CAP_DB=12.0
GMIN=10**(-CAP_DB/20.0)


def stft(x):
    return signal.stft(x,fs=SR,window='hann',nperseg=N_FFT,noverlap=N_FFT-HOP,
                       nfft=N_FFT,boundary='zeros',padded=False)[2]

def istft(z):
    return signal.istft(z,fs=SR,window='hann',nperseg=N_FFT,
                        noverlap=N_FFT-HOP,nfft=N_FFT,boundary=True)[1][:SAMPLES]

def scale_to_db(wave, reference, db):
    r=lambda s: np.sqrt(np.mean(np.square(s))+EPS)
    return wave * (r(reference)/(r(wave)+EPS)) * 10**(db/20)

def build_scene(rng, kind):
    """kind: train, id, overlap, novel_frequency, interference, absent."""
    t=np.arange(SAMPLES,dtype=np.float64)/SR
    fundamental=float(rng.uniform(170,300))
    if kind=='overlap':
        fundamental=float(rng.uniform(430,800))
    if kind=='novel_frequency':
        fundamental=float(rng.uniform(180,420))
    # Synthetic voiced surrogate, deliberately NOT real human speech.
    envelope=0.55+0.45*np.sin(2*np.pi*float(rng.uniform(2,8))*t+float(rng.uniform(-3,3)))**2
    protected=envelope*(0.14*np.sin(2*np.pi*fundamental*t+float(rng.uniform(-3,3)))+
             0.07*np.sin(2*np.pi*fundamental*2*t+0.2)+
             0.035*np.sin(2*np.pi*fundamental*3*t+0.4))
    if kind=='overlap':
        f0=float(rng.uniform(450,780));f1=float(rng.uniform(700,1150))
    elif kind=='novel_frequency':
        f0=float(rng.uniform(1950,2550));f1=float(rng.uniform(2900,4200))
    else:
        f0=float(rng.uniform(700,980));f1=float(rng.uniform(1200,1750))
    chirp=signal.chirp(t,f0=f0,f1=f1,t1=t[-1],method=('quadratic' if kind=='novel_frequency' else 'linear'))
    mod=0.55+0.45*np.sin(2*np.pi*float(rng.uniform(3,8))*t+float(rng.uniform(-3,3)))**2
    target=(chirp*mod).astype(np.float64)
    snr=float(rng.uniform(-7,8))
    if kind=='overlap': snr=float(rng.uniform(-16,-5))
    elif kind=='interference': snr=float(rng.uniform(-15,-2))
    if kind=='absent': target=np.zeros_like(target)
    else: target=scale_to_db(target,protected,snr)
    noise=rng.standard_normal(SAMPLES)
    if kind=='interference':
        # Bursty wideband interference and an independent competing chirp.
        burst=(rng.uniform(0.5,1.0)<0.75)*np.exp(-((t-float(rng.uniform(.04,.24)))/.016)**2)
        noise=0.16*noise*burst+0.09*signal.chirp(t,550, t[-1], 2600)
    elif kind=='novel_frequency':
        noise=0.075*noise+0.08*np.sin(2*np.pi*float(rng.uniform(2100,2900))*t)
    else:
        noise=0.02*noise
    if kind=='absent':
        noise=0.025*noise  # negative case should learn identity
    mix=protected+target+noise
    return mix,protected,target,noise

def scene_features(stems):
    mix,prot,target,noise=stems
    X=stft(mix)
    T=np.abs(stft(target))
    R=np.abs(stft(prot+noise))
    irm=(T/(T+R+EPS)).astype(np.float32).T
    feature=np.log1p(20*np.abs(X).T).astype(np.float32)
    return feature,irm

def network():
    # Identical 236,833-parameter graph to original Keras smoke script.
    magnitude=keras.Input(shape=(FRAMES,BINS),name='log_mix_mag')
    target=keras.Input(shape=(1,),dtype='int32',name='target_class')
    emb=keras.layers.Embedding(input_dim=10,output_dim=16,name='target_embedding')(target)
    emb=keras.layers.Flatten()(emb)
    emb=keras.layers.RepeatVector(FRAMES)(emb)
    x=keras.layers.Concatenate()([magnitude,emb])
    for d in (1,2,4):
        x=keras.layers.Conv1D(128,3,padding='causal',dilation_rate=d,activation='relu',name=f'causal_d{d}')(x)
    mask=keras.layers.Dense(BINS,activation='sigmoid',name='target_mask')(x)
    return keras.Model([magnitude,target],mask,name='hesychia_m4_smoke')

def energy_db(reference,after):
    return float(10*np.log10((np.sum(reference**2)+EPS)/(np.sum(after**2)+EPS)))

def metrics_for_mask(mask,stems):
    mix,prot,target,noise=stems
    gain=np.maximum(1.0-mask.T,GMIN)
    if gain.shape!=(BINS,FRAMES): raise ValueError('wrong gain shape')
    y=istft(gain*stft(mix))
    yp=istft(gain*stft(prot))
    yt=istft(gain*stft(target))
    prot_db=energy_db(prot,yp)
    present=bool(np.max(np.abs(target))>EPS)
    tar_db=energy_db(target,yt) if present else None
    return {'A_protected_db':prot_db,'A_target_db':tar_db,
            'protected_ok':prot_db<=1.0,'target_ok':tar_db is not None and tar_db>=6.0,
            'joint_ok':tar_db is not None and tar_db>=6.0 and prot_db<=1.0,
            'output':y,'gain_min':float(np.min(gain)),
            'mask_mean':float(np.mean(mask))}
