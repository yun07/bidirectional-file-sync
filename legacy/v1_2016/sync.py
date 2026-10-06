import os
from ruamel import yaml
import time
from datetime import datetime
from shutil import copy2
from shutil import rmtree

localDir = r'D:\UserData\Working_Alvin\HoudiniProjects\scenes\tree'
cloudDir = r'O:\VAS\05_2018\ALVIN\sync'

join = os.path.join
cwd = os.getcwd()



def makeList(path):
    currentDir = {}    
    for name in os.listdir(path):        
        filePath = join(path,name)

        if name == 'filelist.yaml':
            pass
        elif not os.path.isdir(filePath):
            currentDir[name] = {'time': datetime.fromtimestamp(os.path.getmtime(filePath)),'isDelet':False,'dir':None}
            # print ('{} is file'.format(name))
        else :
            dirName = name+os.sep
            currentDir[name] = {'time': datetime.fromtimestamp(os.path.getmtime(filePath)),'isDelet':False,'dir':makeList(filePath)}

    return currentDir
    # if len(currentDir) == 0 :
    #     return 'Empty Folder'
    # else :
    #     return currentDir

def file_to_dict(path, name='filelist.yaml'):
    with open(join(path, name ), 'r') as f :
        dict = yaml.load(f, Loader=yaml.RoundTripLoader)
    return dict

def dict_to_file(dict,path,name='filelist.yaml'):
    with open(join(path,name), 'w') as f :
        yaml.dump(dict, f, Dumper=yaml.RoundTripDumper)

def dict_to_txt(dict,path,name='ddd.txt'):
    with open(join(path,name), 'w') as f :
        f.write(str(dict))


def dict_to_set(dict):
    if dict == {}:
        return set([])
    else:
        return set(dict.keys())



def updateList(currentDir={},dirList={}):
    # for name in dict_to_set(dirList):        
    #     if len(dirList[name]) != 3:
    #         dirList[name] = currentDir[name]
    if len(dirList) == 0:
        return currentDir
    for name in dict_to_set(currentDir)&dict_to_set(dirList):
        if currentDir[name]['dir']!=None and dirList[name]['dir']!=None:
            dirList[name]['isDelet'] = False
            dirList[name]['time'] = currentDir[name]['time']            
            dirList[name]['dir']=updateList(currentDir[name]['dir'],dirList[name]['dir'])
        else :
            dirList[name] = currentDir[name]
    for name in dict_to_set(currentDir)-dict_to_set(dirList):
        # print('-------add file or Folder----{}---'.format(name))
        dirList[name] = currentDir[name]
    for name in dict_to_set(dirList)-dict_to_set(currentDir):
        # print('-------delet file or Folder----{}---'.format(name))
        if dirList[name]['isDelet'] == False:
            dirList[name]['isDelet'] = True
            dirList[name]['time'] = datetime.now()
        if dirList[name]['dir']!=None:
            dirList[name]['dir'] = updateList(currentDir={},dirList=dirList[name]['dir'])
    return dirList

def showList(dirList,n=1):
    for name in dirList:
        print('{}{}----{}----{}--'.format(' '*4*n,name,dirList[name]['time'],dirList[name]['isDelet']))
        if dirList[name]['dir'] != None:
            showList(dirList[name]['dir'],n+1)
    
def writeList(path):
    
    currentDir=makeList(path)
    
    

    dirList=currentDir
    if os.path.isfile(join(path, 'filelist.yaml')):        
        dirList = file_to_dict(path)
        dirList=updateList(currentDir,dirList)
    dict_to_file(dirList,path) 
    dirList = file_to_dict(path)
    print('--------------')
    showList(dirList)   
    print('--------------')

def sync(localList={},cloudList={},subDir=''):
    
    localSubDir = join(localDir,subDir)
    cloudSubDir = join(cloudDir,subDir)

    for name in dict_to_set(localList)&dict_to_set(cloudList):
        # if all the flie clear
        if localList[name]['isDelet']==True and cloudList[name]['isDelet']==True:
            localList.pop(name,None)
            cloudList.pop(name,None)
        # if that is Directory
        elif localList[name]['dir']!=None and cloudList[name]['dir']!=None:
            # still here in both side
            if localList[name]['isDelet']==False and cloudList[name]['isDelet']==False:                
                localList[name]['dir'],cloudList[name]['dir'] = sync(localList[name]['dir'],cloudList[name]['dir'],join(subDir,name))
            #  apprear in only one side
            elif localList[name]['time']>cloudList[name]['time']:
                if localList[name]['isDelet'] == True:
                    rmtree(join(cloudSubDir,name))
                else :
                    cloudList[name]['isDelet'] = False
                    localList[name]['dir'],cloudList[name]['dir'] = sync(localList[name]['dir'],cloudList[name]['dir'],join(subDir,name))
            elif localList[name]['time']<cloudList[name]['time']:
                if cloudList[name]['isDelet'] == True:
                    rmtree(join(localSubDir,name))
                else :
                    localList[name]['isDelet'] = False
                    localList[name]['dir'],cloudList[name]['dir'] = sync(localList[name]['dir'],cloudList[name]['dir'],join(subDir,name))

        # if that is file
        elif localList[name]['time']>cloudList[name]['time']:
            if localList[name]['isDelet'] == True:
                os.remove(join(cloudSubDir,name))
            else :
                os.remove(join(cloudSubDir,name))
                copy2(join(localSubDir,name),join(cloudSubDir,name))
        elif localList[name]['time']<cloudList[name]['time']:
            if cloudList[name]['isDelet'] == True:
                os.remove(join(localSubDir,name))
            else :
                os.remove(join(localSubDir,name))
                copy2(join(cloudSubDir,name),join(localSubDir,name))

    for name in dict_to_set(localList)-dict_to_set(cloudList):
        if localList[name]['isDelet']==False:
            if localList[name]['dir']==None:
                copy2(join(localSubDir,name),join(cloudSubDir,name))
            else :
                os.mkdir(join(cloudSubDir,name))
        else :
            localList.pop(name,None)       
    for name in dict_to_set(cloudList)-dict_to_set(localList):
        if cloudList[name]['isDelet']==False:
            if cloudList[name]['dir']==None:
                copy2(join(cloudSubDir,name),join(localSubDir,name))
            else :
                os.mkdir(join(localSubDir,name))
        else :
            cloudList.pop(name,None)   
    return localList, cloudList

   

if __name__ == '__main__':
    while True:
        writeList(localDir)
        writeList(cloudDir)
        
        localList = file_to_dict(localDir)
        cloudList = file_to_dict(cloudDir)
        localList, cloudList = sync(localList,cloudList)
        dict_to_file(localList,localDir)
        dict_to_file(cloudList,cloudDir)
        time.sleep(1)
