"""Prompt 8: refine torso and waist armor while preserving all other assemblies."""
import os, sys, math
import bpy
from mathutils import Vector
ROOT='/home/user/Cavaliere3D'
sys.path.insert(0, os.path.join(ROOT,'tools'))
import build_armor_blockout as A
SRC=os.path.join(ROOT,'Wildshift_Knight_07_Shoulders.blend')
DST=os.path.join(ROOT,'Wildshift_Knight_08_TorsoArmor.blend')

def shell(name, grid, normals, mat, thickness=.006, bevel=.0015):
    return A.make_closed_shell(name,grid,normals,bpy.data.collections['Armor'],mat,thickness,bevel)

def panel(name, theta0, theta1, zlow, zhigh, bulge=0):
    grid=[]; norms=[]
    for i in range(11):
        t=i/10; row=[]; nr=[]
        for j in range(13):
            u=j/12; th=theta0+(theta1-theta0)*u
            z=zlow+(zhigh-zlow)*t
            p,n=A.torso_point(z,th)
            crown=bulge*math.sin(math.pi*u)**2*math.sin(math.pi*t)
            row.append(p+n*(.014+crown)); nr.append(n)
        grid.append(row); norms.append(nr)
    obj=shell(name,grid,norms,bpy.data.materials[A.MAT_IRON],.006,.0012)
    A.set_props(obj,'independent overlapping torso side plate','upper torso','overlaps front and back cuirass edges; articulated seam')
    return obj

def main():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    arm=bpy.data.collections['Armor']
    # Rebuild legacy cuirass forms with a higher central keel and broad shaped pectoral planes.
    for n in ('WSK_Armor_Chest_01','WSK_Armor_Back_01'):
        ob=bpy.data.objects.get(n)
        if ob: bpy.data.objects.remove(ob,do_unlink=True)
    body=bpy.data.objects['WSK_Body_Base_01']
    tree=A.body_bvh(body)
    angles=[-1+2*i/48 for i in range(49)]; rows=[i/20 for i in range(21)]
    def front(s): return 1.105+.073*s**1.6, 1.691-.115*s**1.4
    def rear(s): return 1.105+.068*s**1.6, 1.664-.095*s**1.4
    chest=A.sample_radial_panel(tree,'WSK_Armor_Chest_01',angles,rows,front,side='front',clearance=.014,thickness=.008,ridge=.015,ridge_width=math.radians(12))
    A.set_props(chest,'structured central chest cuirass','chest / upper torso','raised central keel with paired pectoral planes; independent closed 8 mm shell')
    back=A.sample_radial_panel(tree,'WSK_Armor_Back_01',angles,rows,rear,side='rear',clearance=.016,thickness=.008,ridge=.010,ridge_width=math.radians(10))
    A.set_props(back,'sculpted rear cuirass plate','chest / upper torso','separate deep rear shell with spinal ridge and shaped shoulder-blade planes')
    # side lames at both flanks, overlapping the cuirass edges but leaving a waist flex seam
    for sign,label in ((1,'R'),(-1,'L')):
        panel(f'WSK_Armor_SidePlate_{label}_01', math.radians(49),math.radians(131),1.205,1.585,.004)
    # waist belt is a separate contoured band; four discrete fauld/tasset plates hang in front/back.
    def waist_band(name, center, span, z0,z1):
        grid=[]; norms=[]
        for i in range(5):
            t=i/4; row=[]; nr=[]
            for j in range(49):
                th=center-span+2*span*j/48
                z=z0+(z1-z0)*t
                p,n=A.torso_point(z,th); row.append(p+n*.014); nr.append(n)
            grid.append(row); norms.append(nr)
        o=shell(name,grid,norms,bpy.data.materials[A.MAT_IRON],.007,.0015)
        A.set_props(o,'independent waist band','pelvis / waist','separate articulated belt plate, clear of thigh armor')
        return o
    waist_band('WSK_Armor_WaistBelt_01',0,math.radians(82),1.005,1.105)
    # front/rear hanging armor leaves; narrow gaps preserve hip flexion.
    for side,center in [('Front',0),('Rear',math.pi)]:
        for ix,(a,b) in enumerate([(-.78,-.29),(-.24,.24),(.29,.78)]):
            lo=center+a; hi=center+b
            grid=[]; norms=[]
            for i in range(9):
                t=i/8; row=[]; nr=[]
                z=1.015-.105*t
                for j in range(9):
                    th=lo+(hi-lo)*j/8
                    p,n=A.torso_point(z,th)
                    ridge=.004*math.sin(math.pi*j/8)**2*math.sin(math.pi*t)
                    row.append(p+n*(.018+ridge)); nr.append(n)
                grid.append(row); norms.append(nr)
            o=shell(f'WSK_Armor_WaistPanel_{side}_{ix+1:02d}_01',grid,norms,bpy.data.materials[A.MAT_STEEL],.006,.0012)
            A.set_props(o,'separate hanging waist armor panel','pelvis / waist','short articulated fauld panel; clear of upper legs and independent mesh')
    # Simple blank medallion mount only (no emblem): shallow, vertical disk on front belt.
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=.043, depth=.012, location=(0,.137,1.055), rotation=(math.radians(90),0,0))
    med=bpy.context.object; med.name='WSK_Armor_WaistMedallionMount_01'
    # move to Armor collection only
    for c in list(med.users_collection): c.objects.unlink(med)
    arm.objects.link(med); med.data.materials.append(bpy.data.materials[A.MAT_IRON])
    bevel=med.modifiers.new('WSK_Medallion_Rim_Bevel','BEVEL'); bevel.width=.002; bevel.segments=2
    A.set_props(med,'blank central waist medallion mount','pelvis / belt','plain raised mount; symbol intentionally deferred')
    bpy.ops.wm.save_as_mainfile(filepath=DST)
    print('SAVED',DST)
if __name__=='__main__': main()
