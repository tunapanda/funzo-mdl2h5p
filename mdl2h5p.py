
# coding: utf-8


from __future__ import unicode_literals
import lxml
import lxml.etree
import os.path
import json
import youtube_dl


export_dir = "h5p_export"
moodle_dir = "CommonSenseEcon.mbz-expanded/"
h5p_template_dirs = {
    "CoursePresentation" : "H5P_CoursePresentation-template",
}

# TODO: This is a total hack. Need include some js magic or something
# that gets the appropriate base URL from the host instead
h5p_assets_url_base = "/courses/funzo-CSE-1000/modules/module-2/"

# credit: http://pythoncentral.io/how-to-recursively-copy-a-directory-folder-in-python/ 
import errno
import shutil
import re
 
def copy(src, dest):
    try:
        shutil.copytree(src, dest)
    except OSError as e:
        # If the error was caused because the source wasn't a directory
        if e.errno == errno.ENOTDIR:
            shutil.copy(src, dest)
        else:
            print('Directory not copied. Error: %s' % e)
            
def unescape_html(s):
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&amp;", "&")
    return s

import urllib2
filesxml = lxml.etree.parse(os.path.join(moodle_dir,"files.xml"))
def download_link_target(url,basedir,content_type="files",force=False):
    content_dir = os.path.join("content",content_type)
    dn = os.path.join(basedir,content_dir)
    if not os.path.exists(dn):
        os.makedirs(dn)
    fn = os.path.basename(url)
    dst = os.path.join(dn,fn)
    print "XXX DL %s to %s" % (fn,dst)
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
    return "/".join([h5p_assets_url_base,content_dir,fn])


def download_video(url,basedir,content_type="files"):
    global fn
    content_dir = os.path.join("content",content_type)
    dn = os.path.join(basedir,content_dir)
    if not os.path.exists(dn):
        os.makedirs(dn)      
    urlinfo = urllib2.urlparse.urlparse(url)
    fn = "-".join([urlinfo.netloc] + urlinfo.path.split("/"))
    dst = os.path.join(dn,fn)
    print "***\nDOWNLOADING VIDEO\n  URL: %s\n  DST: %s\n***" % (url,dst)
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
            print "XXX failed to DL %s" % fn
    relative_url = os.path.join(h5p_assets_url_base,content_dir,fn)
    print "Returning: %s" % relative_url
    return relative_url



import uuid
import shutil

class _H5PContent(object):
    def __init__(self,src,auto_save=False,force_fresh=False):
        self._content_dict = None
        self.src     = src
        if auto_save:
            self.save(force_fresh=force_fresh)
        
    def __repr__(self):
        return self.content_json
        
    def save(self,baseDir=None,force_fresh=False):
        if baseDir is None:
            baseDir = os.path.join(export_dir,self.src.title)
        contentDir = os.path.join(baseDir,"content")
        if os.path.exists(baseDir) and force_fresh:
            print "XXX Removing existing dir: %s" % baseDir
            shutil.rmtree(baseDir)
        if not os.path.exists(baseDir):
            print "XXX copying template to %s" % baseDir
            copy(h5p_template_dirs["CoursePresentation"],baseDir)
        print "XXX Downloading media..."
        self.src.fetch_media(baseDir,recursive=True)
        print "XXX Populating content.json..."
        content_fh = open(os.path.join(contentDir,"content.json"),"w")
        content_fh.write(self.content_json)
        content_fh.close()
        print "XXX DONE."
            
    @property
    def content_json(self):
        return json.dumps(self.content)
            
    @property
    def content(self):
        if self._content_dict is None:
            self._content_dict = self._generate_content_dict()
        return self._content_dict
    
    # Override in subclasses!
    def _generate_content_dict(self):
        return {}
        
    # Not used in most cases
    def add_child(self,child_h5p):
        pass
    
class H5PCoursePresentation(_H5PContent):                
    def _generate_content_dict(self):
        content = {}
        content["presentation"] = {}
        slides = []
        for child_h5p in self.src.to_h5p():
            slides.append({
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
              })
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
         
    def _gen_subContentId(self):
        return str(uuid.uuid1())
    

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
                if ext.startswith("."):
                    ext = ext[1:]
                if ext in download_extensions:
                    local_fn = download_link_target(url,baseDir)
                    n.set(p,local_fn)
                    files.append(local_fn)

                elif getattr(self,"title",None) is not None:
                    if self.title.startswith("Watch:"):
                        local_fn = download_video(url,baseDir)
                        n.set(p,local_fn)
                        files.append(local_fn)
        return (files,content_xmltree) 
        
    def to_h5p(self):
        h5p = []
        h5p.append(self._h5pClass(self))
        #print "XXX %s generates %s" % (self,type(h5p))
        for child in self.children:
            h5p += child.to_h5p()
        return h5p
        
    @property
    def text(self):
        if self._text is None:
            self._text = "\n".join([ getattr(self,c) for c in self._content_nodes if getattr(self,c,None) is not None ])
        return self._text
    

class MoodleSection(_MoodleContent):
    contentType = "section"
    _base_property_names = ["sectionid","title","directory"]
    _extended_property_names = ["summary"]
    _content_nodes = ["summary"]
    _h5pClass = H5PAdvancedText

    def _get_children(self):
        children = []
        # Note: "//" causes this search to start from the passed <section>'s
        #       xml root (top-level parent), not (just) from the section its self.
        for axml in self.root_xmltree.xpath("//activities/activity[sectionid = %s]" % self.sectionid):
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

    def _get_children(self):
        questions_fn = os.path.join(moodle_dir,"questions.xml")
        questions_xml = lxml.etree.parse(questions_fn)
        children = []
        for qixml in self.extended_xmltree.xpath(".//question_instance"):
            qid = qixml.find("questionid").text
            qxml = questions_xml.xpath("/question_categories/question_category/questions/question[@id=%s]" % qid)[0]
            try:
                mod = moodle_question_factory(qxml)
            except UnknownMoodleQuestionTypeException,e:
                print e
                continue
            children.append(mod)
        return children
        
class _MoodleQuestion(_MoodleModule):
    _base_property_names = ["name","questiontext","qtype"]
    _content_nodes = ["questiontext"]
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
        "folder" : MoodleFolder,
        "forum" : MoodleForum,
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



e = lxml.etree.parse(moodle_dir + "moodle_backup.xml")
s = MoodleSection(e.xpath("//sections/section")[1])
h = H5PCoursePresentation(s)
h.save()


