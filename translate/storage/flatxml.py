# -*- coding: utf-8 -*-

"""Module for handling flat XML files."""

from lxml import etree

from translate.lang import data
from translate.misc.xml_helpers import getText, namespaced
from translate.storage import base
from translate.storage.placeables import general


class FlatXMLUnit(base.TranslationUnit):
    """A single term in the XML file."""

    element_name = "str"
    attribute_name = "key"
    namespace = None
    rich_parsers = general.parsers

    def __init__(self, source=None,
                 namespace=None, element_name="str", attribute_name="key",
                 **kwargs):
        self.namespace = namespace
        self.element_name = element_name
        self.attribute_name = attribute_name
        self.element = etree.Element(self.namespaced(self.element_name))
        super(FlatXMLUnit, self).__init__(source, **kwargs)

    def __str__(self):
        # "unicode" encoding keeps the unicode status of the output
        return etree.tostring(self.element, encoding="unicode")

    @property
    def source(self):
        """Returns the unique identifier of this unit."""
        return self.element.get(self.attribute_name)

    @source.setter
    def source(self, source):
        """Updates the unique identifier of this unit."""
        self.element.set(self.attribute_name, source)

    def gettarget(self):
        """Returns the translated string of this unit."""
        return self.node_text

    def settarget(self, target):
        """Updates the translated string of this unit."""
        super(FlatXMLUnit, self).settarget(target)
        target = data.forceunicode(target)
        if self.target == target:
            return
        self.element.text = target

    # Weblate requires the settarget method,
    # so we cannot use the @property syntax here.
    target = property(gettarget, settarget)

    def namespaced(self, name):
        """Returns name in Clark notation."""
        return namespaced(self.namespace, name)

    @property
    def node_text(self):
        """Returns the text content of the XML element."""
        if self.element is None:
            return None

        return getText(self.element)

    @classmethod
    def createfromxmlElement(cls, element,
                             namespace=None,
                             element_name="str",
                             attribute_name="key"):
        """Attempts to create a unit from the passed element.

        element must not be None and must match the given element name
        (including namespace); otherwise None will be returned.
        """
        if element is None:
            return None
        if element.tag != namespaced(namespace, element_name):
            return None
        unit = cls(source=None,
                   namespace=namespace,
                   element_name=element_name,
                   attribute_name=attribute_name)
        unit.element = element
        return unit


class FlatXMLFile(base.TranslationStore):
    """Class representing a flat XML file store"""

    UnitClass = FlatXMLUnit
    _name = "Flat XML File"
    Mimetypes = ["text/xml"]
    Extensions = ["xml"]

    def __init__(self,
                 inputfile=None,
                 sourcelanguage="en",
                 targetlanguage=None,
                 root_name="root",
                 value_name="str",
                 key_name="key",
                 namespace=None,
                 indent_chars="  ",
                 **kwargs):
        self.root_name = root_name
        self.value_name = value_name
        self.key_name = key_name
        self.namespace = namespace
        self.indent_chars = indent_chars

        super(FlatXMLFile, self).__init__(**kwargs)
        if inputfile is not None:
            self.parse(inputfile)
        else:
            self.make_empty_file()
            self.setsourcelanguage(sourcelanguage)
            self.settargetlanguage(targetlanguage)

    def addunit(self, unit, new=True):
        unit.namespace = self.namespace
        super(FlatXMLFile, self).addunit(unit)
        if new:
            self.root.append(unit.element)

    def reindent(self):
        """Reindents the backing document to be consistent."""
        # no elements? nothing to do.
        if not(len(self.root)):
            pass

        # ensure trailing EOL for VCS
        self.root.tail = "\n"

        if self.indent_chars is None:
            # indent None means: linearize
            self.root.text = None
            for child in self.root:
                child.tail = None
        else:
            per_level_indent = "\n" + self.indent_chars
            # root indent is done with its text property
            self.root.text = per_level_indent
            # indent all but the last element, its tail
            # would indent the closing tag of the root element.
            for child in self.root[:-1]:
                child.tail = per_level_indent
            self.root[-1].tail = "\n"

    def serialize(self, out=None):
        self.reindent()
        self.document.write(out, xml_declaration=True, encoding=self.encoding)

    def make_empty_file(self):
        """Initializes the backing document to be an empty root element."""
        self.root = etree.Element(self.namespaced(self.root_name))
        self.document = self.root.getroottree()

    def parse(self, xml):
        """Parses the passed xml file into the backing document."""
        if not hasattr(self, "filename"):
            self.filename = getattr(xml, "name", "")
        if hasattr(xml, "read"):
            xml.seek(0)
            posrc = xml.read()
            xml = posrc

        parser = etree.XMLParser(strip_cdata=False, resolve_entities=False)
        self.root = etree.fromstring(xml, parser)
        self.document = self.root.getroottree()
        self.encoding = self.document.docinfo.encoding

        root_name = self.namespaced(self.root_name)
        assert self.root.tag == root_name, \
            "expected root name to be %s but got %s" % (root_name, self.root.tag)
        if len(self.root):
            # we'd expect at least one child element to have the correct
            # name and attributes; otherwise the name parameters might've
            # been wrong/typo'd and need to be addressed in order to avoid
            # coming up empty when the file actually contains entries.
            value_name = self.namespaced(self.value_name)
            matching_nodes = list(self.root.iterchildren(value_name))
            assert len(matching_nodes), \
                "expected value name to be %s but first node is %s" % (
                    value_name, self.root[0].tag)

            assert matching_nodes[0].get(self.key_name), \
                "expected key attribute to be %s, found attribute(s): %s" % (
                    self.key_name, ",".join(matching_nodes[0].attrib))

        for entry in self.root:
            unit = self.UnitClass.createfromxmlElement(
                entry,
                namespace=self.namespace,
                element_name=self.value_name,
                attribute_name=self.key_name)
            if unit is not None:
                self.addunit(unit, new=False)

    def namespaced(self, name):
        """Returns name in Clark notation."""
        return namespaced(self.namespace, name)
