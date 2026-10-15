"""Strict non-adjacent triangle crossings, excluding shared-vertex contact."""
import numpy as np

def crossings(points, triangles, active):
    vertices=points[triangles]
    lower=vertices.min(axis=1);upper=vertices.max(axis=1)
    pairs=[]
    for start in range(0,len(active),64):
        selected=active[start:start+64]
        overlap=((lower[selected,None,:]<upper[None,:,:]-1e-9)&
                 (upper[selected,None,:]>lower[None,:,:]+1e-9)).all(axis=2)
        ii,jj=np.nonzero(overlap)
        a=selected[ii];b=jj
        distinct=(triangles[a,:,None]!=triangles[b,None,:]).all(axis=(1,2))
        if distinct.any():pairs.append(np.sort(np.stack((a[distinct],b[distinct]),axis=1),axis=1))
    if not pairs:return set()
    pairs=np.unique(np.concatenate(pairs),axis=0)
    a=vertices[pairs[:,0]];b=vertices[pairs[:,1]]
    hits=np.zeros(len(pairs),dtype=bool)
    def segment_hit(start,end,tri):
        direction=end-start;e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0]
        h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
        inverse=np.divide(1.,det,out=np.zeros_like(det),where=np.abs(det)>1e-10)
        offset=start-tri[:,0];u=inverse*np.einsum('ij,ij->i',offset,h)
        q=np.cross(offset,e1);v=inverse*np.einsum('ij,ij->i',direction,q)
        t=inverse*np.einsum('ij,ij->i',e2,q);eps=1e-7
        return (np.abs(det)>1e-10)&(u>eps)&(v>eps)&(u+v<1-eps)&(t>eps)&(t<1-eps)
    for index in range(3):
        hits|=segment_hit(a[:,index],a[:,(index+1)%3],b)
        hits|=segment_hit(b[:,index],b[:,(index+1)%3],a)
    return {tuple(pair) for pair in pairs[hits].tolist()}
