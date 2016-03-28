# coding: utf-8

from __future__ import unicode_literals
import errno
import json
import lxml, lxml.etree
import os, os.path
import re
import shutil
import sys
import urllib2
import uuid
import youtube_dl

# Regexes that match URLs which should be treated as video 
# download sites.
video_url_re = [
    re.compile(r".*criticalcommons\.org.*clips/.*"),
]
h5p_library_re = re.compile(r"H5P\.(.*) (\d+)\.(\d+)")

export_dir = "h5p_export"
moodle_dir = "CommonSenseEcon.mbz-expanded/"
h5p_template_dirs = {
    "CoursePresentation" : "H5P_CoursePresentation-template",
}

debugLevel = 3
def dbg(msg,level=3):
    """Print debig messages, depending on how the debugLevel global is set"""
    if level >= debugLevel:
        sys.stderr.write("* DBG:\n* DBG: XXX %x\n* DBG: XXX\n" % msg)

def json_pp(content):
    """Pretty-print a JSON representation of the given content"""
    return json.dumps(
            content,
            sort_keys=True,
            indent=4,
            separators=(',', ': ')
        )

# credit: http://pythoncentral.io/how-to-recursively-copy-a-directory-folder-in-python/ 
def copy(src, dst):
    """Recursively copy src to dst (can also copy regular files)"""
    try:
        shutil.copytree(src, dst)
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(src, dst)
        else:
            print('Directory not copied. Error: %s' % e)
            
def unescape_html(s):
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&amp;", "&")
    return s

filesxml = lxml.etree.parse(os.path.join(moodle_dir,"files.xml"))
def download_link_target(url,basedir,content_type="files",force=False):
    """Download url target to BASEDIR/content/CONTENT_TYPE/..."""
    content_dir = os.path.join("content",content_type)
    dn = os.path.join(basedir,content_dir)
    if not os.path.exists(dn):
        os.makedirs(dn)
    fn = os.path.basename(url)
    dst = os.path.join(dn,fn)
    dbg("DL %s to %s" % (fn,dst))
    if not os.path.exists(dst) or force:
        urlinfo = urllib2.urlparse.urlparse(url)
        if urlinfo.scheme == "":
            # Look up contentHash associated with fn in files.xml
            # copy files/ab/abcd1234..., rename to fn
            fn = os.path.basename(url)
            mdlfn = filesxml.xpath("//file[filename='%s']" % fn)[0].findtext("contenthash")
            src = os.path.join(moodle_dir,"files",mdlfn[0:2],mdlfn)
            copy(src,dst)
        else:
            open(dst, "w").write(urllib2.urlopen(url).read())
    # Return an absolute URL that should work for this file within funzo
    return os.path.join(content_type,fn)


def download_video(url,basedir,content_type="files"):
    """Like download_link_target, but specialized for video pages"""
    global fn
    content_dir = os.path.join("content",content_type)
    dn = os.path.join(basedir,content_dir)
    if not os.path.exists(dn):
        os.makedirs(dn)      
    urlinfo = urllib2.urlparse.urlparse(url)
    fn = "-".join([urlinfo.netloc] + urlinfo.path.split("/"))
    dst = os.path.join(dn,fn)
    dbg("DOWNLOADING VIDEO\n  URL: %s\n  DST: %s" % (url,dst),4)
    def ydl_hooks(d):
        global fn
        if d['status'] == 'finished':
            # Update to get extension provided by the downloader
            fn = os.path.basename(d['filename'])
    ydl_opts = {
        "max_downloads": 1,
        "outtmpl": dst + ".%(ext)s",
        "progress_hooks": [ydl_hooks],
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            ret = ydl.download([url])
        except youtube_dl.MaxDownloadsReached:
            pass
        except youtube_dl.DownloadError:
            dbg("failed to DL %s" % fn)
    relative_url = os.path.join(content_type,fn)
    dbg("Returning: %s" % relative_url,4)
    return relative_url


def save_h5p(h5p,baseDir=None,force_fresh=False):
    if baseDir is None:
        baseDir = os.path.join(export_dir,h5p.title)
    contentDir = os.path.join(baseDir,"content")
    if os.path.exists(baseDir) and force_fresh:
        dbg("Removing existing dir: %s" % baseDir, 4)
        shutil.rmtree(baseDir)
    if not os.path.exists(baseDir):
        #dbg("copying template to %s" % baseDir)
        #copy(h5p_template_dirs["CoursePresentation"],baseDir)
        dbg("Creating H5P base dir %s" % baseDir, 4)
        os.mkdir(baseDir)
    dbg("Downloading media...")
    h5p.fetch_media(baseDir,recursive=True)
    dbg("Populating content.json...")
    content_fh = open(os.path.join(contentDir,"content.json"),"w")
    content_fh.write(h5p.content_json)
    content_fh.close()
    dbg("Populating h5p.json...")
    # TODO: copy required libraries (`preloadedDependencies`) in
    # h5p_json from some known location into baseDir? 
    h5p_fh = open(os.path.join(baseDir,"h5p.json"),"w")
    h5p_fh.write(h5p.h5p_json)
    h5p_fh.close()
    dbg("DONE.")

class H5PCoursePresentation(object): 
    library = "H5P.CoursePresentation 1.7"
    def __init__(self, title):
        self.title = title
        self._content_dict = None
        self.slides = []
        
    def fetch_media(self,baseDir,recursive=True):
        res = []
        for child_h5p in self._get_slides():
            res += child_h5p.fetch_media(baseDir,recursive)
        return res
        
    def add_slides(self, child_h5ps):
        if hasattr(child_h5ps,"__iter__"):
            self.slides += child_h5ps
        else:
            self.slides.append(child_h5p)
    
    def _get_slides(self):
        #return self.src.to_h5p()
        return self.slides
        
    @property
    def h5p_json(self):
        return json_pp(self.package_dict)
        
    @property
    def package_dict(self):
        if self._package_dict is None:
            self._package_dict = {
                  "title": self.title,
                  "language": "und",
                  "mainLibrary": self.library.split()[0],
                  "embedTypes": [
                    "div"
                  ],
                  "preloadedDependencies": []
            }
            for h5p in [self] + self.slides:
                lib_string = getattr(h5p,"library",None)
                if lib_string is None:
                    continue
                (machineName,majorVersion,minorVersion) = h5p_library_re.match(lib_string)
                self._package_dict["preloadedDependencies"].append({
                  "machineName": machineName,
                  "majorVersion": majorVersion,
                  "minorVersion": minorVersion
                })
        return self._package_dict
            
    @property
    def content_json(self):
        return json_pp(self.content)                
            
    @property
    def content(self):
        if self._content_dict is None:
            self._content_dict = self._generate_content_dict()
        return self._content_dict
           
    def _gen_subContentId(self):
        return str(uuid.uuid1())
    
    def _generate_slide_dict(self,child_h5p):
        return {
                "elements": [
                  {
                    "x": 1,
                    "y": 1,
                    "width": 98,
                    "height": 98,
                    "action": {
                        "library": child_h5p.library, 
                        "params" : child_h5p.content,
                        "subContentId": self._gen_subContentId(),
                    },
                    "alwaysDisplayComments": False,
                    "backgroundOpacity": 0,
                    "displayAsButton": False,
                    "invisible": False,
                    "solution": ""
                  }
                ],
                "keywords": []
              }
    
    def _generate_content_dict(self):
        content = {}
        content["presentation"] = {}
        slides = [{
                "elements": [
                  {
                    "x": 1,
                    "y": 1,
                    "width": 98,
                    "height": 98,
                    "action": {
                        "library": "H5P.AdvancedText 1.1", 
                        "params" : {
                            "text" : "<h1>"+self.title+"</h1>"
                        },
                        "subContentId": self._gen_subContentId(),
                    },
                    "alwaysDisplayComments": False,
                    "backgroundOpacity": 0,
                    "displayAsButton": False,
                    "invisible": False,
                    "solution": ""
                  }
                ],
                "keywords": []
              }]
        for child_h5p in self._get_slides():
            slides.append(self._generate_slide_dict(child_h5p))
        content["presentation"]["slides"] = slides
        
        content["l10n"] = {
            "slide": "Slide",
            "yourScore": "Your Score",
            "maxScore": "Max Score",
            "goodScore": "Congratulations! You got @percent correct!",
            "okScore": "Nice effort! You got @percent correct!",
            "badScore": "You got @percent correct.",
            "Total": "Total",
            "showSolutions": "Show solutions",
            "retry": "Retry",
            "title": "Title",
            "author": "Author",
            "lisence": "Lisence",
            "license": "License",
            "exportAnswers": "Export text",
            "copyright": "Rights of use",
            "hideKeywords": "Hide keywords list",
            "showKeywords": "Show keywords list",
            "fullscreen": "Fullscreen",
            "exitFullscreen": "Exit fullscreen",
            "prevSlide": "Previous slide",
            "nextSlide": "Next slide",
            "currentSlide": "Current slide",
            "lastSlide": "Last slide",
            "solutionModeTitle": "Exit solution mode",
            "solutionModeText": "Solution Mode",
            "summaryMultipleTaskText": "Multiple tasks",
            "scoreMessage": "You achieved:",
            "shareFacebook": "Share on Facebook",
            "shareTwitter": "Share on Twitter",
            "summary": "Summary",
            "solutionsButtonTitle": "Show comments",
            "printTitle": "Print",
            "printIngress": "How would you like to print this presentation?",
            "printAllSlides": "Print all slides",
            "printCurrentSlide": "Print current slide"
          }
        content["override"] = {
            "activeSurface": False,
            "overrideButtons": False,
            "overrideShowSolutionButton": False,
            "overrideRetry": False,
            "hideSummarySlide": False
          }
        return content

class _H5PContent(object):
    def __init__(self,src,auto_save=False,force_fresh=False):
        self._content_dict = None
        self.src     = src
        if auto_save:
            save_h5p(self,force_fresh=force_fresh)
        
    def __repr__(self):
        return self.content_json
        
    @property
    def title(self):
        return self.src.title
            
    @property
    def content_json(self):
        return json_pp(self.content) 
            
    @property
    def content(self):
        if self._content_dict is None:
            self._content_dict = self._generate_content_dict()
        return self._content_dict
        
    def fetch_media(self,baseDir,recursive=True):
        return self.src.fetch_media(baseDir,recursive)
    
    # Override in subclasses!
    def _generate_content_dict(self):
        return {}
    
class H5PAdvancedText(_H5PContent):
    library = "H5P.AdvancedText 1.1"
    def _generate_content_dict(self):
        content = {
            "text": self.src.text,
          }
        return content
    
# TODO:
class H5PEssayQuestion(_H5PContent):
    library = "H5P.AdvancedText 1.1"
    def _generate_content_dict(self):
        content = {
            "text": "<h2>This is dummy text</h2><h3>An essay q will go here</h3>",
          }
        return content

class H5PMultipleChoice(_H5PContent):
    library = "H5P.MultiChoice 1.5"
    def _generate_content_dict(self):
        true = True
        false = False
        answers = []
        for a in self.src.answers:
            answers.append({
                "correct": a.correct,
                "tipsAndFeedback": {
                  "tip": "",
                  "chosenFeedback": "",
                  "notChosenFeedback": ""
                },
                "text": a.text
              })
            
        content = {
            "media": {
              "params": {}
            },
            "answers": answers,
            "UI": {
              "checkAnswerButton": "Check",
              "showSolutionButton": "Show solution",
              "tryAgainButton": "Retry",
              "correctText": "Correct!",
              "almostText": "Almost!",
              "wrongText": "Wrong"
            },
            "behaviour": {
              "enableRetry": true,
              "enableSolutionsButton": true,
              "type": "auto",
              "singlePoint": true,
              "randomAnswers": true,
              "showSolutionsRequiresInput": true,
              "disableImageZooming": false
            },
            "question": self.src.text
        }
        return content



class _MoodleContent(object):
    # Moodle module type ("section", "page", "quiz", etc)
    contentType = None
    # Properties from moodle_backup.xml
    _base_property_names = ["sectionid","title","directory"]
    # Properties from <mod_type_dir>/<mod_id>/<mod_type>.xml
    _extended_property_names = []
    # Properties that contain HTML
    _content_nodes = []
    # If true, render this content as a new .h5p by default
    start_new = False
    
    def __init__(self,xmltree):
        self._children = None
        self._text = None
        self.root_xmltree = xmltree
        self.extended_xmltree = None # this gets set at the end
        for p in self._base_property_names:
            v = self.root_xmltree.find(p).text
            setattr(self, p, v)
        self._set_extended_properties()
        
    def _set_extended_properties(self):
        if len(self._extended_property_names) == 0:
            return
        sourcefn = moodle_dir + "%s/%s.xml" % (self.directory,self.contentType)
        sourcexml = lxml.etree.parse(sourcefn).xpath("//" + self.contentType)[0]
        self.extended_xmltree = sourcexml
        for p in self._extended_property_names:
            content = sourcexml.find(p).text
            setattr(self, p, content)
                
    def __repr__(self):
        title = "%s/%s" % (type(self),self.contentType)
        if self.title is not None:
            title += " %s" % self.title
        title += " with %s children" % len(self.children)
        return title
    
    @property
    def title(self):
        if hasattr(self,"_title"):
            return self._title
        elif hasattr(self,"name"):
            return self.name
        else:
            return None
    
    @title.setter
    def title(self,value):
        self._title = value
         
    @property
    def children(self):
        if self._children is None:
            self._children = self._get_children()
        return self._children  
    
    def _get_children(self):
        return []
        
    
    def fetch_media(self,baseDir,recursive=True):
        fetched_files = []
        for n in self._content_nodes:
            content = getattr(self,n,None)
            if content is None:
                continue
            content_xmltree = lxml.etree.HTML("<html>%s</html>" % content)
            (files,revised_xmltree) = self._fetch_media(baseDir,content_xmltree)
            
            # The above probably updated link targets, so we 
            # need to update the stored xmltree. To do this, we must
            # strip out the <html><body> that was added to the original
            # self.content to make it parseable by lxml
            revised_content = ""
            for e in revised_xmltree[0][:]:
                revised_content += lxml.etree.tostring(e)
            setattr(self,n,revised_content)
            
            fetched_files += files
        if recursive:
            for c in self.children:
                fetched_files += c.fetch_media(baseDir=baseDir,recursive=recursive)
        return fetched_files
    
    def _fetch_media(self,baseDir,content_xmltree):
        download_extensions = ("png","jpg","docx","pdf","png","mp3","mp4")
        files = []
        if content_xmltree is None:
            return files
        links = {}
        links["href"] = content_xmltree.xpath("//*[@href]")
        links["src"]  = content_xmltree.xpath("//*[@src]")
        for (p,nodes) in links.items():
            for n in nodes:
                url = n.get(p)
                ext = os.path.splitext(url)[-1]
                local_fn = None
                if ext.startswith("."):
                    ext = ext[1:]
                if ext in download_extensions:
                    local_fn = download_link_target(url,baseDir)
                elif getattr(self,"title",None) is not None:
                    # CSE-specific
                    if self.title.startswith("Watch:"):
                        local_fn = download_video(url,baseDir)
                if local_fn is None:
                    for regex in video_url_re:
                        if regex.match(url):
                            local_fn = download_video(url,baseDir)
                            break
                if local_fn is None:
                    dbg("Ignoring non-downloadable URL %s" % url) 
                else: 
                    n.set(p,local_fn)
                    classes = n.get("class","")
                    # CSE-specific
                    classes = classes.remove("external")
                    classes += " mdl2h5p_local_content"
                    n.set("class",classes)
                    files.append(local_fn)
        return (files,content_xmltree) 
        
    def to_h5p(self):
        h5p = []
        h5p.append(self._h5pClass(self))
        #dbg("%s generates %s" % (self,type(h5p)))
        for child in self.children:
            h5p += child.to_h5p()
        return h5p
        
    @property
    def text(self):
        if self._text is None:
            self._text = ""
            if self.title is not None:
                self._text += "<h1>%s</h1>" % self.title
            self._text += "\n".join([ getattr(self,c) for c in self._content_nodes if getattr(self,c,None) is not None ])
        return self._text
    

class MoodleSection(_MoodleContent):
    contentType = "section"
    _base_property_names = ["sectionid","title","directory"]
    _extended_property_names = ["summary","sequence"]
    _content_nodes = ["summary"]
    _h5pClass = H5PAdvancedText

    def _get_children(self):
        children = []
        # Note: "//" causes this search to start from the passed <section>'s
        #       xml root (top-level parent), not (just) from the section its self.
        for activity_id in self.sequence.split(","):
            axml = self.root_xmltree.xpath("//activities/activity[moduleid = %s]" % activity_id)[0]
            try:
                mod = moodle_module_factory(axml)
            except UnknownMoodleModuleException,e:
                print "\n***\n%s\n***\n" % e
                mod = _MoodleModule(axml)
            children.append(mod)
        return children
            
class _MoodleModule(_MoodleContent):
    _base_property_names = _MoodleContent._base_property_names + ["moduleid","modulename"]
    _h5pClass = H5PAdvancedText
    
    @property
    def contentType(self):
        return self.modulename
    
class MoodlePage(_MoodleModule):
    _extended_property_names = ["intro","content"]
    _content_nodes = ["intro","content"]

class MoodleLabel(_MoodleModule):
    _extended_property_names = ["name","intro"]
    _content_nodes = ["intro"]

# TODO
class MoodleAssign(_MoodleModule):
    _extended_property_names = ["name","intro"]
    _content_nodes = ["intro"]

class MoodleFolder(_MoodleModule):
    pass

class MoodleForum(_MoodleModule):
    # Ignore these for online standalone course?
    pass

class MoodleQuiz(_MoodleModule):
    _extended_property_names = ["name","intro"]
    _content_nodes = ["intro"]
    start_new = True
    
    @property
    def title(self):
        return "Quiz: %s" % self.name
    
    @title.setter
    def title(self,value):
        self._title = value

    def _get_children(self):
        questions_fn = os.path.join(moodle_dir,"questions.xml")
        questions_xml = lxml.etree.parse(questions_fn)
        children = []
        
        # Store a list of questions explicitly associated with the 
        # quiz so we know not to substitute them for questions with
        # qtype "random"
        used_question_IDs = []  
        for qixml in self.extended_xmltree.xpath(".//question_instance"):
            qid = qixml.find("questionid").text
            used_question_IDs.append(qid)
            
        # This will store questions that...
        # - Are not explicitly associated with the quiz, and
        # - Do not have qtype "random"
        available_questions_by_category = {}
        
        for qixml in self.extended_xmltree.xpath(".//question_instance"):
            qid = qixml.find("questionid").text
            qxml = questions_xml.xpath(
                "/question_categories/question_category/questions/question[@id=%s]" % qid
            )[0]
              
            if qxml.find("qtype").text == "random":
                category_xml = qxml.xpath(
                    "ancestor::question_category"
                )[0]
                category_id = category_xml.get("id")
                if not available_questions_by_category.has_key(category_id):
                    available_questions_by_category[category_id] = {}
                    for q in category_xml.xpath(".//question[qtype != 'random']"):
                        if q.get("id") not in used_question_IDs:
                            available_questions_by_category[category_id][q.get("id")] = q
                try:
                    (qid,qxml) = available_questions_by_category[category_id].popitem()
                except KeyError:
                    dbg("ERROR: more random questions than non-random in category %s?" % category_id)
                    continue
            try:
                mod = moodle_question_factory(qxml)
            except UnknownMoodleQuestionTypeException,e:
                print e
                continue
            children.append(mod)
        return children
        
class _MoodleQuestion(_MoodleModule):
    _base_property_names = ["name","questiontext","qtype"]
    _content_nodes = ["intro","questiontext"]
    #_questionText = None
    _h5pClass = None # replace in subclasses
        
    #@property 
    #def questionText(self):
    #    if self._questionText is None:
    #        self._questionText = self.root_xmltree.find("questiontext").text
    #    return self._questionText
    
    @property
    def contentType(self):
        return self.qtype
        
    @property
    def text(self):
        if self._text is None:
            self._text = ""
            self._text += "\n".join([ getattr(self,c) for c in self._content_nodes if getattr(self,c,None) is not None ])
        return self._text
        
    
    def __repr__(self):
        return "Question" #"Question from XML:\n%s" % lxml.etree.tostring(self.root_xmltree)
    
class MoodleQuestionMulti(_MoodleQuestion):
    _h5pClass = H5PMultipleChoice
    
    @property
    def answers(self):
        return [ MoodleQuestionAnswer(x) for x in self.root_xmltree.xpath(".//answers/answer") ]
    
class MoodleQuestionEssay(_MoodleQuestion):
    _h5pClass = H5PEssayQuestion

class MoodleUrl(_MoodleModule):
    _extended_property_names = ["name","intro", "externalurl"]
    _content_nodes = ["intro"]

class MoodleQuestionAnswer(object):
    def __init__(self,xmlroot):
        self.root_xmltree = xmlroot
        self._text = None
        self._correct = None
        
    @property
    def text(self):
        if self._text is None:
            self._text = self.root_xmltree.find("answertext").text
        return self._text
        
    @property
    def correct(self):
        if self._correct is None:
            if float(self.root_xmltree.find("fraction").text) > 0:
                self._correct = True
            else:
                self._correct = False
        return self._correct

# Factory function for generating an object of the appropriate class, 
# given the xml node of a Moodle <activity> from moodle_backup.xml
class UnknownMoodleModuleException(Exception):
    pass

class UnknownMoodleQuestionTypeException(Exception):
    pass

def moodle_module_factory(module_xml):
    module_classes = {
        "assign": MoodleAssign,
        #"folder" : MoodleFolder,
        #"forum" : MoodleForum,
        "label" : MoodleLabel,
        "page"  : MoodlePage,
        "quiz"  : MoodleQuiz,
        "url"   : MoodleUrl,
    }
    modulename = module_xml.find("modulename").text
    if module_classes.has_key(modulename):
        return module_classes[modulename](module_xml)
    else: 
        raise UnknownMoodleModuleException("Don't know how to handle '%s' modules" % modulename)
        
def moodle_question_factory(question_xml):
    question_classes = {
        "multichoice" : MoodleQuestionMulti,
        "essay" : MoodleQuestionEssay,
    }
    qtype = question_xml.find("qtype").text
    if question_classes.has_key(qtype):
        return question_classes[qtype](question_xml)
    else: 
        raise UnknownMoodleQuestionTypeException("Don't know how to handle '%s' quiz questions" % qtype)

def moodle2h5p(
        moodle_dir,
        export_dir=export_dir,
        course_name=None,
        course_category="Misc"
    ):
    e = lxml.etree.parse(os.path.join(
            moodle_dir,
            "moodle_backup.xml"
        ))
    if course_name is None:
        cfn = e.xpath("//original_course_fullname")[0].text
        ver = e.xpath("//backup_version")[0].text
        course_name = "%s-%s" % (cfn,ver)
    section_number = 0
    for s in e.xpath("//sections/section")[1:3]:
        section_number += 1
        section_id = s.find("sectionid").text
        #title = s.find("title").text
        #h5p_toplevels = [H5PCoursePresentation(title)]
        h5p_toplevels = []
        activities = s.xpath("//activities/activity[sectionid = %s]" % section_id)
        force_new = True
        for i in range(0,len(activities)):
            axml = activities[i]
            try:
                mod = moodle_module_factory(axml)
            except UnknownMoodleModuleException,e:
                print "\n***\n%s\n***\n" % e
                continue
            if mod.start_new:
                # New toplevel for this activity
                title = mod.title
                h5p_toplevels.append(H5PCoursePresentation(title))
                force_new = True
            # New toplevel for 1st activity, or after a start_new
            elif force_new: 
                title = "Watch, Read, and Listen"
                h5p_toplevels.append(H5PCoursePresentation(title))
                force_new = False
            h5p_toplevels[-1].add_slides(mod.to_h5p())
        courseBaseDir = os.path.join(export_dir,course_name)
        moduleBaseDir = os.path.join(courseBaseDir,"modules")
        course_modules = []
        for i in range(0,len(h5p_toplevels)):
            h = h5p_toplevels[i]
            module_number = i + 1
            moduleFullName = "%s-%s-%s" % (
                section_number,
                module_number,
                h.title
            )
            h = h5p_toplevels[i]
            moduleDir = os.path.join(moduleBaseDir,moduleFullName)
            course_modules.append({
              "title": moduleFullName,
              "permalink": os.path.basename(moduleDir)
            })
            save_h5p(h, baseDir=moduleDir)
        course_content_fn = os.path.join(
            courseBaseDir,
            "content.json"
        )
        
        # TODO: This shouldn't be necessary, but for
        # some reason if you don't remove the old file,
        # new content gets appended instead of (over)writing
        try:
            os.unlink(course_content_fn)
        except OSError:
            pass
        course_content_fh = open(course_content_fn,"w")
        course_content_fh.write(json_pp(
            {
              "title": course_name + " (funzo-mdl2h5p)",
              "subject": course_category,
              "permalink": os.path.basename(courseBaseDir),
              "modules": course_modules
            }
        ))
    

if __name__ == "__main__":
    moodle_dir = "CommonSenseEcon.mbz-expanded"
    course_category = "Economics"
    moodle2h5p(moodle_dir,course_category=course_category)



