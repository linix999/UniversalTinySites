# -*- coding: utf-8 -*-
# @Time    : 3/14/19 6:39 PM
# @Author  : linix

import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup

import sys
import win32com.client
import pythoncom
import redis
import threading
import MySQLdb
import logging
import re

from UniversalTinySitesSettings import inputFieldFeatures,searchBtnFeatures,tagExcludeFeatures,resultsFeatures,whiteSites
sys.path.append("..")
import utils

isServer=0
#logging.getLogger().setLevel(logging.INFO)

class SearchSites():
    def __init__(self,mainPageUrl):
        """
        driverpath='C:\phantomjs-1.9.8\phantomjs.exe'
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36"
        cap = webdriver.DesiredCapabilities.PHANTOMJS
        cap["phantomjs.page.settings.resourceTimeout"] = 200000
        cap["phantomjs.page.settings.loadImages"] = True
        cap["phantomjs.page.settings.disk-cache"] = True
        cap["phantomjs.page.settings.userAgent"] = ua
        cap["phantomjs.page.customHeaders.User-Agent"] =ua
        self.driver = webdriver.PhantomJS(executable_path=driverpath,desired_capabilities=cap, service_args=['--ignore-ssl-errors=true','--ssl-protocol=TLSv1'])
        """
        driverpath='E:\Tools\ChromePortable\chromedriver.exe'
        options = webdriver.ChromeOptions()
        options.add_argument('lang=zh_CN.UTF-8')
        #options.add_argument('user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"')
        #option.add_argument('headless')
        self.mainPage=mainPageUrl
        self.inputFieldFeatures=inputFieldFeatures
        self.searchBtnFeatures=searchBtnFeatures
        self.matchInputFeature=self.matchBtnFeature=None
        self.matchInputIndex=self.matchBtnIndex=0
        self.db=DbOpt()
        self.driver=None
        try:
            self.driver = webdriver.Chrome(executable_path=driverpath,chrome_options=options)
            self.driver.set_page_load_timeout(30)
            self.driver.maximize_window()
            self.ready,self.originWindow=self.openMainPage()
        except BaseException as e:
            self.ready=False
            self.originWindow=None

    def openMainPage(self):
        windowHandle=None
        try:
            self.driver.get(self.mainPage)
            login=WebDriverWait(self.driver,10).until(
                EC.presence_of_element_located((By.XPATH,"//title"))
                )
            if u'无法访问' in self.driver.title or '404' in self.driver.title:
                ready=False
            else:
                ready=True
                windowHandle=self.driver.current_window_handle
        except Exception as e:
            ready=False
        return ready,windowHandle

    def search(self,searchProjects):
        isMatch=False
        isFirst=True
        siteBestResult=4
        for project in searchProjects:
            projectId=project[0]
            keywords=project[1]
            whiteWords=project[2]
            needWords=project[3]
            for kw in keywords:
                if self.ready and (isFirst or isMatch):
                    if not isFirst:
                        self.ready,windowHandle=self.openMainPage()
                    try:
                        inputField,searchBtn=self.findPageTag(self.driver,isFirst)
                        if inputField and searchBtn:
                            inputField.click()
                            time.sleep(float(random.randint(1,3))/10)
                            inputField.clear()
                            for c in kw:
                                inputField.send_keys(c)
                                time.sleep(float(random.randint(1,3))/10)
                            time.sleep(float(random.randint(1,3))/10)
                            searchBtn.click()   #点击后可能出现很多情况，弹窗，弹页面，新标签...
                            time.sleep(float(random.randint(5,12))/10)
                            handles=self.driver.window_handles
                            for handle in handles:
                                self.driver.switch_to.window(handle)
                                searchResults=self.parsePage(self.driver.page_source,projectId,kw,whiteWords,needWords)
                                if searchResults<siteBestResult:
                                    siteBestResult=searchResults
                                if handle!=self.originWindow:
                                    self.driver.close()
                                    self.driver.switch_to.window(self.originWindow)
                        else:
                            logging.info(u'主页找不到输入框及搜索按钮。网址为：%s' % self.mainPage)
                            searchResults=4
                    except BaseException as e:
                        logging.info(u'查找主页输入框及搜索按钮失败！网址为：%s' %self.mainPage)
                        searchResults=4
                else:
                    logging.info(u'网站打不开或重定向！网址为：%s' %self.mainPage)
                    if not ('searchResults' in dir()):
                        siteBestResult=searchResults=3
                if isFirst and searchResults<3:
                    isMatch=True
                isFirst=False

        self.db.recordSiteSearchResults([self.mainPage,siteBestResult])
        self.close()

    def parsePage(self,html,projectId,keyword,whiteWords,needWords):
        bsobj = BeautifulSoup(self.driver.page_source, "html.parser")
        black=False if needWords else True
        white=False
        bestResult=2
        for resultFeature in resultsFeatures:
            if resultFeature[1] and resultFeature[2]:
                resultTags=bsobj.find_all(resultFeature[0],attrs={resultFeature[1]:re.compile(resultFeature[2],re.IGNORECASE)})
            else:
                resultTags=bsobj.find_all(resultFeature[0])
            seachResults=1 if len(resultTags) else 2
            try:
                for eachUl in resultTags:
                    title=tagText=content=u''
                    tagText=eachUl.string if eachUl.string else eachUl.text
                    content+=tagText
                    for item in eachUl.descendants:
                        tagText = item.string if item.string else item.text
                        content+=tagText
                        if len(title)<1:
                            if utils.getUnicode(keyword) in utils.getUnicode(tagText):
                                title=tagText.strip()
                    for word in needWords:
                        if word in content:
                            black=True
                            break
                    if utils.getUnicode(keyword) in utils.getUnicode(tagText) and len(title)<1:
                        title=tagText.strip()
                    for word in whiteWords:
                        if word in content:
                            white=True
                            break
                    if title and black and not white:
                        title=title.replace("\r","").replace("\n","").replace("\t","")[:500]
                        link=eachUl.find("a").attrs['href'] if eachUl.find("a") else ''
                        if link:
                            if self.mainPage.rstrip('/').lstrip('https://').lstrip('http://').lstrip('www.') not in link and '//www.' not in link:
                                link=self.mainPage.rstrip('/')+'/'+link.lstrip('/')
                            timeStr=time.strftime("%Y-%m-%d",time.localtime(time.time()))
                            results=[u'小网站搜索',keyword,self.driver.current_url,link,title,timeStr,projectId]
                            self.db.insertResults(results)
                            seachResults=0
            except BaseException as e:
                pass
            if seachResults<bestResult:
                bestResult=seachResults
        return bestResult

    def findPageTag(self,driver,isFirst):
        seleniumStrPatt="//{tag}[contains(@{type_},'"
        inputField=searchBtn=None
        try:
            bsobj = BeautifulSoup(self.driver.page_source, "html.parser")
            if isFirst:
                for inputFeature in self.inputFieldFeatures:
                    #bsInputField=bsobj.find(inputFeature[0],attrs={inputFeature[1]:inputFeature[2]})
                    bsInputFields=bsobj.find_all(inputFeature[0],attrs={inputFeature[1]:re.compile(inputFeature[2],re.IGNORECASE)})
                    for index,bsInputField in enumerate(bsInputFields):
                        if not inputField:
                            #inputFieldStr=seleniumStrPatt.format(tag=inputFeature[0],type_=inputFeature[1])
                            #inputField=self.driver.find_element_by_xpath(inputFieldStr+inputFeature[2]+"')]")
                            isBadTag=False
                            for k,v in bsInputField.attrs.items():
                                for badTag in tagExcludeFeatures:
                                    if badTag in v:
                                        isBadTag=True
                            if not isBadTag:
                                inputFieldStr=seleniumStrPatt.format(tag=inputFeature[0],type_=inputFeature[1])+inputFeature[2][1:]+"')]"
                                try:
                                    inputField=self.driver.find_elements_by_xpath(inputFieldStr)[index]
                                    if inputField:
                                        self.matchInputFeature=inputFeature
                                        self.matchInputIndex=index
                                except:
                                    inputField=None
                for searchBtnFeature in self.searchBtnFeatures:
                    #bsSearchBtn=bsobj.find(searchBtnFeature[0],attrs={searchBtnFeature[1]:searchBtnFeature[2]})
                    bsSearchBtns=bsobj.find_all(searchBtnFeature[0],attrs={searchBtnFeature[1]:re.compile(searchBtnFeature[2],re.IGNORECASE)})
                    for index, bsSearchBtn in enumerate(bsSearchBtns):
                        if not searchBtn:
                            #searchBtnStr=seleniumStrPatt.format(tag=searchBtnFeature[0],type_=searchBtnFeature[1])
                            #searchBtn=self.driver.find_element_by_xpath(searchBtnStr+searchBtnFeature[2]+"')]")
                            isBadTag=False
                            for k,v in bsSearchBtn.attrs.items():
                                for badTag in tagExcludeFeatures:
                                    if badTag in v:
                                        isBadTag=True
                            if not isBadTag:
                                searchBtnStr=seleniumStrPatt.format(tag=searchBtnFeature[0],type_=searchBtnFeature[1])+searchBtnFeature[2][1:]+"')]"
                                try:
                                    searchBtn=self.driver.find_element_by_xpath(searchBtnStr)
                                    if searchBtn:
                                        self.matchBtnFeature=searchBtnFeature
                                        self.matchBtnIndex=index
                                except:
                                    searchBtn=None
            elif self.matchInputFeature and self.matchBtnFeature:
                inputFieldStr=seleniumStrPatt.format(tag=self.matchInputFeature[0],type_=self.matchInputFeature[1])+self.matchInputFeature[2][1:]+"')]"
                inputField=self.driver.find_elements_by_xpath(inputFieldStr)[self.matchInputIndex]
                searchBtnStr=seleniumStrPatt.format(tag=self.matchBtnFeature[0],type_=self.matchBtnFeature[1])+self.matchBtnFeature[2][1:]+"')]"
                searchBtn=self.driver.find_elements_by_xpath(searchBtnStr)[self.matchBtnIndex]
            else:
                inputField=searchBtn=None

        except BaseException as e:
            logging.info(u'查找主页输入框及搜索按钮失败！网址为：%s' %self.mainPage)
            inputField=searchBtn=None
        return inputField,searchBtn

    def close(self):
        if self.db:
            self.db.close()
        try: #单quit关不掉
            if self.driver:
                handles=self.driver.window_handles
                for handle in handles:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                    time.sleep(float(random.randint(1,2))/10)
                self.driver.quit()
        except BaseException as e:
            pass

class DbOpt():
    def __init__(self):
        self.host = '192.168.1.119'
        self.user = 'root'
        self.pwd = ''
        self.port = 3306
        self.charset = 'utf8'
        self.db = 'intelliwatch'
        self.conn=None
        self.conn=self.connectMySQL()
        if self.conn:
            self.cur=self.conn.cursor()

    def connectMySQL(self):
        try:
            if self.conn is not None:
                self.conn.commit()
                self.cur.close()
                self.conn.close()
            conn = MySQLdb.Connect(host=self.host,
                                            port=self.port,
                                            user=self.user,
                                            passwd=self.pwd,
                                            db=self.db,
                                            charset=self.charset)
        except BaseException, e:
            logging.info(u'连接数据库报错，原因为：%s',e)
        return conn

    def getTinySites1(self,limit,offset):
        try:
            self.cur.execute(
                """select count(*) as cnt,left(targetUrl,LOCATE('/',targetUrl,8)) as site from web_searchresult where platform in (select name from web_platform where typename='搜索')  and targetUrl like %s  GROUP BY site ORDER BY cnt DESC LIMIT %s OFFSET %s""",
                ('http%',limit, offset))
            return self.cur.fetchall()
        except BaseException,e:
            logging.info(u'查询侵权小网站SQL语句报错，原因为：%s', e)

    def getTinySites(self,limit,offset):
        try:
            self.cur.execute(
                """select searchResultType,siteUrl from tinySitesSearchRecord where searchResultType=2 or searchResultType=1 """)
            return self.cur.fetchall()
        except BaseException,e:
            logging.info(u'查询侵权小网站SQL语句报错，原因为：%s', e)

    def getSearchWords(self):
        try:
            self.cur.execute("""select projectId,projectName,searchKeywords,whiteWords,needWords from tinySitesSearchSetting""")
            return self.cur.fetchall()
        except BaseException,e:
            logging.info(u'查询项目搜索关键字SQL语句报错，原因为：%s', e)

    def insertResults(self,results):
        try:
            self.cur.execute("""select targetUrl from web_searchspider_results where  targetUrl=%s""",(results[3],))
            records=self.cur.fetchone()
            if not records or len(records)==0:
                self.cur.execute(
                    """insert into web_searchspider_results (platform,keyword,resultUrl,targetUrl,targetTitle,createDate,project_id,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (results[0], results[1], results[2], results[3], results[4],results[5],results[6],0))
                self.conn.commit()
        except BaseException, e:
            logging.error(u"数据库插入记录出错,%s", e)
            self.conn.rollback()

    def recordSiteSearchResults(self,results):
        timeStr=time.strftime("%Y-%m-%d",time.localtime(time.time()))
        if int(results[1])==0:
            resultText=u'网站搜索到结果'
        elif int(results[1])==1:
            resultText=u'网站搜索到内容但没有想要的'
        elif int(results[1])==2:
            resultText=u'网站搜索内容为空'
        elif int(results[1])==3:
            resultText=u'网站打开失败'
        elif int(results[1])==4:
            resultText=u'网站可以打开，但没有找到通用搜索标签'
        else:
            resultText=u'其他情况'
        try:
            self.cur.execute("""select siteUrl from tinySitesSearchRecord where siteUrl=%s""",(results[0],))
            records=self.cur.fetchone()
            if records and len(records):
                self.cur.execute("""update tinySitesSearchRecord set searchResult=%s,searchResultType=%s,lastSearchTime=%s where siteUrl=%s and searchResultType>%s""", (resultText,results[1],timeStr,results[0],results[1],))
            else:
                self.cur.execute("""insert into tinySitesSearchRecord (siteUrl,searchResult,searchResultType,lastSearchTime) VALUES (%s,%s,%s,%s)""",
                    (results[0], resultText,results[1],timeStr))
            self.conn.commit()
        except BaseException, e:
            logging.error(u"数据库插入记录出错,%s", e)
            self.conn.rollback()

    def close(self):
        if self.conn:
            try:
                self.cur.close()
                self.conn.close()
            except BaseException as e:
                pass

class Manager():
    def __init__(self,runBatch):
        self.redisHost = '192.168.1.119'
        self.redisPort = 6379
        self.spiderName='tinySitesSpider'
        self.startUrls='%(spider)s:StartUrls'
        self.redisConn=redis.Redis(host=self.redisHost,port=self.redisPort)
        self.redisPoolMin=20000
        self.sqlBatch = 50000
        self.sqlCurPos=0
        self.isPushedAll=False
        self.runBatch=runBatch
        self.db=DbOpt()
        self.whiteSites=whiteSites

    def getSearchSettings(self):
        keywords=self.db.getSearchWords()
        return keywords

    def pushTinySites(self):
        while not self.isPushedAll:
            if  self.redisConn.llen(self.startUrls % {'spider': self.spiderName})<self.redisPoolMin:
                tinySites=self.db.getTinySites(self.sqlBatch,self.sqlCurPos)
                self.sqlCurPos+=len(tinySites)
                if len(tinySites)==0:
                    self.isPushedAll=True
                for i in range(len(tinySites)):
                    if len(tinySites[i][1].strip().strip('http').strip('//'))>5:
                        needPush=True
                        for site in self.whiteSites:
                            if site in tinySites[i][1]:
                                needPush=False
                                break
                        if needPush:
                            self.redisConn.lpush(self.startUrls % {'spider': self.spiderName},tinySites[i][1])
                            #self.redisConn.lpush(self.startUrls % {'spider': self.spiderName},'http://www.zhandi.cc/')

    def run(self,searchSettings):
        searchProjects=[]
        for i in range(len(searchSettings)):
            projectId=searchSettings[i][0]
            kws=searchSettings[i][2].split('|') if searchSettings[i][2] else []
            whiteWords=searchSettings[i][3].split('|') if searchSettings[i][4] else []
            needWords=searchSettings[i][4].split('|') if searchSettings[i][4] else []
            searchProjects.append([projectId,kws,whiteWords,needWords])
        site=self.redisConn.rpop(self.startUrls % {'spider': self.spiderName})
        #site='http://xw.kandy999.com/'
        if site:
            browser=SearchSites(site)
            browser.search(searchProjects)
            time.sleep(0.1)
        else:
            time.sleep(5)

    def isDone(self):
        if self.redisConn.llen(self.startUrls % {'spider': self.spiderName})<1 and self .isPushedAll:
            return True
        return False

    def close(self):
        if self.db:
            self.db.close()

def findChromeNums():
    pythoncom.CoInitialize()
    try:
        wmi=win32com.client.GetObject('winmgmts:')
        chromeNums=0
        for p in wmi.InstancesOf('Win32_Process'):
            children=wmi.ExecQuery('Select * from win32_process where ParentProcessId=%s' %p.Properties_('ProcessId'))
            for child in children:
                if child.Name=='Chromedriver.exe' or child.Name=='chromedriver.exe':
                    chromeNums+=1
    except BaseException as e:
        chromeNums=0
    finally:
        #pythoncom.CoUninitialize()
        return chromeNums


if __name__ == '__main__':

    runBatch=4
    manager=Manager(runBatch)
    searchSettings=manager.getSearchSettings()

    if isServer:
        redisThread=threading.Thread(target=manager.pushTinySites)
        redisThread.start()

    while not manager.isDone():
        chromeNums=findChromeNums()
        if chromeNums<runBatch:
            t=threading.Thread(target=manager.run,args=(searchSettings,))
            t.start()
        time.sleep(0.5)

    if isServer:
        redisThread.stop()
    manager.close()