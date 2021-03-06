# coding: utf-8
"""
WIKTIONARY_PARSER:

    Contains WiktionaryParser class for parsing Wiktionary entries in any language.
"""
import os
import re
import string
import json
import requests
from BeautifulSoup import BeautifulSoup
from ordered_set import OrderedSet
from ipa_symbols import *


class WiktionaryParser:
    """
    A class for parsing Wiktionary pages.
    """
    PATH = os.path.dirname(os.path.realpath(__file__))
    LANG_CODES = {u"Afrikaans": "af",
                  u"Albanian": 'sq',
                  u"Arabic": "ar",
                  u"Armenian": "hy",
                  u"Basque": 'eu',
                  u"Bengali": "bn",
                  u"Bosnian": 'bs',
                  u"Breton": 'br',
                  u"Bulgarian": 'bg',
                  u"Catalan": 'ca',
                  u"Chinese": "zh",
                  u"Croatian": 'hr',
                  u"Danish": 'da',
                  u"Dutch": 'nl',
                  u"English": 'en',
                  u"Esperanto": 'eo',
                  u"Georgian": 'ka',
                  u"German": 'de',
                  u"Greek": 'el',
                  u"Finnish": 'fi',
                  u"French": 'fr',
                  u"Galician": 'gl',
                  u"Hebrew": 'he',
                  u"Hindi": 'hi',
                  u"Hungarian": "hu",
                  u"Icelandic": 'is',
                  u"Indonesian": 'id',
                  u"Italian": 'it',
                  u"Japanese": 'ja',
                  u"Kazakh": 'kk',
                  u"Korean": 'ko',
                  u"Latvian": "lv",
                  u"Lithuanian": "lt",
                  u"Macedonian": "mk",
                  u"Malayan": "ml",
                  u"Malay": "ms",
                  u"Norwegian": 'no',
                  u"Persian": 'fa',
                  u"Polish": 'pl',
                  u"Portuguese": 'pt',
                  u"Romanian": 'ro',
                  u"Russian": 'ru',
                  u"Serbian": 'sr',
                  u"Sinhala": 'si',
                  u"Slovak": 'sk',
                  u"Slovenian": 'sl',
                  u"Spanish": 'es',
                  u"Swedish": 'sv',
                  u"Tamil": 'ta',
                  u"Telugu": 'te',
                  u"Thai": 'th',
                  u"Tagalog": 'tl',
                  u"Turkish": 'tr',
                  u"Ukrainian": 'uk',
                  u"Vietnamese": 'vi'}
    PARTS_OF_SPEECH = {u"Noun", u"Verb", u"Adjective", u"Adverb", u"Preposition",
                       u"Conjunction", u"Interjection", u"Morpheme", u"Pronoun",
                       u"Phrase", u"Numeral", u"Particle", u"Article", u"Participle",
                       u"Prefix", u"Suffix", u"Circumfix", u"Interfix", u"Infix"}
    WIKI_URL = "https://en.wiktionary.org"
    END_URL = "/w/index.php?title=Category:%s"
    BASE_URL = WIKI_URL + "/wiki/%s#%s"
    IPA_PATH = "_terms_with_IPA_pronunciation&from="
    LEMMA_PATH = "_lemmas"
    STRESS_MARKS = u"ˈˌ"
    HEADERS = ["h1",  # page word
               "h2",  # word language entry
               "h3",  # language subentry 1 (e.g. Etymology)
               "h4",  # language subentry 2 (e.g. Etymology->Pronoun)
               "h5"]  # language subentry 3 (e.g. Etymology->Pronoun->Declension)
    HEADER_NAMES = PARTS_OF_SPEECH.union({"Pronunciation",
                                          "Etymology",
                                          "Declension"})

    def __init__(self):
        self.session = requests.session()
        self.url = self.WIKI_URL + self.END_URL
        self.language = None
        self.wiktionary_entries = self.fetch_wiktionary_entries()

        # REGEXES
        self.html_pattern = re.compile("(<.+?>|\n)") # used to include |\d
        self.quote_pattern = re.compile("\"[^\+]*?\"")
        self.paren_pattern = re.compile("\([^\(]*?\)")
        self.deriv_pattern = re.compile('(\S+ ?([("]+.+[")]+)? ?\+\S* ?)+[^.]+ ?(\".+?\")?')
        self.space_pattern = re.compile("( )+")

    def verify_language(self, language):
        """
        If given language is None, returns self.language.
        Otherwise, returns given language.

        :param language: str, language to verify
        :return: str, verified language
        """
        if language is None:
            return self.language
        else:
            return language

    def valid_ipa(self, ipa):
        """
        Returns True if this IPA pronunciation contains only
        valid IPA symbols.
        ~
        Used for rooting out invalid IPA symbols.

        :param ipa: unicode, IPA pronunciation to verify
        :return: bool, whether given IPA is valid
        """
        return ipa[0] != "-" and self.ipaize(ipa) == ipa

    def get_lang_code(self, language=None):
        """
        Returns the language code associated with the given language.
        ~
        e.g. get_lang_code("Polish") -> "pl"

        :param language: str, language to retrieve language code for
        :return: str, language code for given language
        """
        language = self.verify_language(language)
        return self.LANG_CODES.get(language, None)

    # JSON
    # ----
    def dump_json(self, data, filename):
        """
        Dumps data (prettily) to filename.json.

        :param data: X, data to dump to JSON
        :param filename: str, name of .json file to dump to
        :return: None
        """
        path = self.PATH + "/resources/data/" + filename + ".json"
        json.dump(data, open(path, 'w'), indent=1, sort_keys=True, encoding='utf-8')

    def fetch_json(self, filename):
        """
        Returns a dictionary corresponding to the given JSON file.

        :param filename: str, name of .json file to fetch
        :return: X, content of given .json file
        """
        path = self.PATH + "/resources/data/" + filename + ".json"
        return json.load(open(path))

    def fetch_wiktionary_entries(self):
        """
        Returns a dictionary of memoized Wiktionary pages.

        :return: dict(str, dict), where str is a word and dict is...
            key (str) - language of word entry
            val (dict) - language's entry under word
        """
        return self.fetch_json("wiktionary_entries")

    def refresh_wiktionary_entries(self):
        """
        Dumps this WiktionaryParser's wiktionary_entries data to
        wiktionary_entries.json.

        :return: None
        """
        self.dump_json(self.wiktionary_entries, "wiktionary_entries")

    # WIKTIONARY PAGES
    # ----------------
    def entry_word(self, word, language=None):
        """
        Returns the correctly capitalized version of this word
        which has an entry in wiktionary_entries.

        :param word: str, word to find entry word for
        :param language: str, language of given word
        :return: str, entry word for given word
        """
        language = self.verify_language(language)
        nuwords = [word, word.lower(), word.title()]

        for nuword in nuwords:
            try:
                self.wiktionary_entries[nuword][language]
            except KeyError:
                continue
            else:
                return nuword

        return word

    def add_wiktionary_entries(self, words, language=None):
        """
        Adds Wiktionary entries for these words to this
        WiktionaryParser's wiktionary_entries.

        :param words: List[str], words of Wiktionary entries to add
        :param language: str, language of entries to add
        :return: dict(str, dict), where str is language and dict is...
            key (str) - title of subentry heading (e.g. Etymology)
            val (list) - value(s) associated with subentry
        """
        language = self.verify_language(language)
        for word in words:
            if word not in self.wiktionary_entries:
                print word
                print self.find_wiktionary_entry(word, language)
                print
        return self.wiktionary_entries

    def add_wiktionary_entry(self, word, language=None):
        """
        Adds a Wiktionary entry corresponding to the given word
        to this WiktionaryParser's wiktionary_entries.

        :param word: str, word of Wiktionary entry to add
        :param language: str, language of entry to add
        :return: dict(str, dict), where str is language and dict is...
            key (str) - title of subentry heading (e.g. Etymology)
            val (list) - value(s) associated with subentry
        """
        word = self.unicodize(word)
        language = self.verify_language(language)
        wikt_page = WiktionaryPage(word, language=language, parser=self)
        entries = wikt_page.entries
        word = self.entry_word(word, language)
        self.wiktionary_entries.setdefault(word, dict())
        self.wiktionary_entries[word].update(entries)
        return entries.get(language, entries)

    def edit_wiktionary_entry(self, word, language=None, heading=None, content=None):
        """
        Edits the Wiktionary entry for this word by adding this content
        under this language and heading.

        :param word: str, word of Wiktionary entry to edit
        :param language: str, language of entry to edit
        :param heading: str, heading of entry to edit
        :param content: List[str], content to add to entry
        :return: None
        """
        word = self.unicodize(word)
        language = self.verify_language(language)
        entry = self.lookup_wiktionary_subentry(word, language)
        heading_entry = entry.setdefault(heading, list())

        try:
            self.wiktionary_entries[word][language].setdefault(heading, list())
        except KeyError:
            return
        else:
            entry = self.wiktionary_entries[word][language][heading]
            self.wiktionary_entries[word][language][heading] = OrderedSet(entry + content).items()

    def contains_punct(self, word):
        """
        Returns True if any punctuation characters are in this word.

        :param word: str, word to check whether containing punctuation
        :return: bool, whether punctuation in this word or not
        """
        return any(char in word for char in string.punctuation)

    # LOOKUPS & FINDS
    # ---------------
    # Use lookup to "look up" existing entries,
    # use find to "find" new entries if none exist.
    # ---------------
    def find_wiktionary_entry(self, word, language=None):
        """
        If a Wiktionary page corresponding to this word already
        exists, returns the memoized page.  Otherwise, retrieves new
        Wiktionary page data for word and adds new entry to this
        WiktionaryParser's wiktionary_entries.

        :param word: str, word of Wiktionary page to lookup
        :param language: str, language of entry to lookup
        :return: dict(str, dict), where str is language and dict is...
            key (str) - title of subentry heading (e.g. Etymology)
            val (list) - value(s) associated with subentry
        """
        entry = self.lookup_wiktionary_entry(word, language)
        if entry is not None:
            return entry
        else:
            entry = self.wiktionary_entries.get(word, dict())
            entry = entry.get(language, None)
            if entry is None and word is not None and not self.contains_punct(word):
                entry = self.add_wiktionary_entry(word, language)
            return entry

    def lookup_wiktionary_entry(self, word, language=None):
        """
        If a Wiktionary page corresponding to this word already
        exists, returns the memoized page.  Otherwise, returns None.

        :param word: str, word of Wiktionary page to lookup
        :param language: str, language of entry to lookup
        :return: dict(str, dict), where str is language and dict is...
            key (str) - title of subentry heading (e.g. Etymology)
            val (list) - value(s) associated with subentry
        """
        language = self.verify_language(language)
        try:
            return self.wiktionary_entries[word][language]
        except KeyError:
            return

    def find_wiktionary_subentry(self, word=None, language=None, heading=None):
        """
        Returns the Wiktionary subentry for the given word, language and/or heading.
        ~
        If word is not None, this method returns the sub-entry for this
        word.
        ~
        If language is not None, this method returns the sub-entry
        for this language.
        ~
        If heading is not None, this method returns all sub-entries with
        this heading for this word in this language.
        ~
        If no entry contains the parameters given, returns an empty dict.
        ~
        e.g. find_wiktionary_subentry("is", "Afrikaans", "Pronunciation") -> [u"əs"]
             find_wiktionary_subentry("is", heading="Pronunciation") ->
                [u"əs", u"i\u02d0s", u"s", u""a\u026az", ...]
             find_wiktionary_subentry("is", "Afrikaans") ->
                {"Pronunciation": [u"əs"],
                 "Verb": [["is", null],
                          ["am , are , is ( present tense, all persons, plural and singular of wees , to be )", null],
                          ["Forms the perfect passive voice when followed by a past participle", null]]}

        :param word: Optional[str], word of Wiktionary page to lookup
        :param language: Optional[str], language of entry to lookup
        :param heading: Optional[str], heading of subentry to lookup
        :return: Any, subentry corresponding to given word, language, &/or heading
        """
        if word is None:
            return self.wiktionary_entries
        elif self.contains_punct(word):
            return

        if language is None:
            return self.find_wiktionary_entry(word)
        else:
            entry = self.find_wiktionary_entry(word, language)
            if heading is None:
                return entry
            else:
                section = entry.get(heading, None)
                if section is not None:
                    return section
                else:
                    for section in entry:
                        if section[:len(heading)] == heading:
                            return entry[section]
        return

    def lookup_wiktionary_subentry(self, word=None, language=None, heading=None):
        try:
            entry = self.wiktionary_entries[word]
            if language is not None:
                entry = entry[language]
                if heading is not None:
                    entry = entry[heading]
        except KeyError:
            return
        else:
            return entry

    def find_headwords(self, word, language=None, poses=None):
        """
        Returns this word's head words from its Wiktionary entry
        in this language.
        ~
        N.B. A "head word" is the first item in the first sublist
        under a word's part-of-speech heading:

            e.g. "Noun": [["miles", None], ["plural of mile", "mile"]]
                            ^^^^^
                          head word

        Part-of-speech entries contain only 1 head word but may
        contain >=1 stem words.

        :param word: str, word of Wiktionary entry to lookup
        :param language: Optional[str], language of entry to lookup
        :return: List[str], given word's head words for this language
        """
        if poses is None:
            poses = self.PARTS_OF_SPEECH

        language = self.verify_language(language)
        headwords = list()
        lang_entries = self.find_wiktionary_entry(word, language)

        for heading in lang_entries:
            if heading in poses:
                pos_entry = lang_entries[heading]
                try:
                    headword = pos_entry[0][0]
                except IndexError:
                    continue
                else:
                    if headword is not None:
                        headwords.append(headword)

        return headwords

    def find_stemwords(self, word, language=None, poses=None):
        """
        Returns this word's stem words from its Wiktionary entry
        in this language.
        ~
        N.B. A "stem word" is the second item in all but the first sublist
        under a word's part-of-speech heading:

            e.g. "Noun": [["miles", None], ["plural of mile", "mile"]]
                                                               ^^^^
                                                             stem word

        Entries may contain >=1 stem words but will only contain 1 head word.

        :param word: str, word of Wiktionary entry to lookup
        :param language: Optional[str], language of entry to lookup
        :return: List[str], given word's stem words for this language
        """
        if poses is None:
            poses = self.PARTS_OF_SPEECH

        language = self.verify_language(language)
        stemwords = list()
        lang_entries = self.find_wiktionary_entry(word, language)

        if lang_entries is not None:
            for heading in lang_entries:
                if heading in poses:
                    pos_entries = lang_entries[heading]
                    try:
                        stems = [pos_entry[1] for pos_entry in pos_entries[1:]
                                 if pos_entry[1] is not None]
                    except IndexError:
                        continue
                    else:
                        stemwords += stems

            return stemwords

    # PAGES
    # -----
    def word_url(self, word):
        """
        Returns a Wiktionary URL for the given word.

        :param word: str, word to retrieve URL for
        :return: str, URL matching given word
        """
        return self.BASE_URL % (word, self.language)

    def url_page(self, url):
        """
        Parses given URL string to a BeautifulSoup Tag.

        :param url: str, URL to parse to tags
        :return: Tag, parsed URL
        """
        response = self.session.get(url)
        html = response.text
        parsed = BeautifulSoup(html)
        return parsed

    def word_page(self, word):
        """
        Returns a BeautifulSoup Tag corresponding to the Wiktionary
        page for the given word.

        :param word: str, word to retrieve page for
        :return: Tag, BeautifulSoup tag matching given word's page
        """
        return self.url_page(self.word_url(word))

    def valid_word_page(self, word, language=None):
        """
        Returns True if this word has a Wiktionary page,
        False otherwise.

        :param page: str, word for a Wiktionary page entry
        :return: bool, whether page is valid
        """
        return self.valid_page(self.word_page(word), language)

    def find_page_language(self, page, language):
        """
        Returns the first span on this page in this language.

        :param page: Tag, HTML Wiktionary page in BeautifulSoup
        :param language: str, language to find on page
        :return: Tag, first HTML span from page in language
        """
        return page.find("span", attrs={"class":"mw-headline", "id":language})

    def valid_page(self, page, language=None):
        """
        Returns True if the given Wiktionary page is valid,
        False otherwise.

        :param page: Tag, HTML Wiktionary page for an entry
        :return: bool, whether page is valid
        """
        if language is None:
            return page.find("h2").getText()[:10] != "Navigation"
        else:
            return self.find_page_language(page, language) is not None

    def word_languages(self, word):
        """
        Returns a list of the given word's Wiktionary entry's languages.

        :param word: str, word of Wiktionary entry to retrieve languages for
        :return: List[str], all languages for this word's Wiktionary entry
        """
        entry = self.find_wiktionary_entry(word)
        return sorted(entry.keys())

    # PAGE PARSING
    # ------------
    def page_ipas(self, page):
        """
        Returns a list of strings of all IPAs from this Wiktionary page
        in BeautifulSoup.

        :param page: BeautifulSoup.Tag, Wiktionary page to fetch IPAs from
        :return: List[unicode], IPAs from this page
        """
        ipa_tags = [ipa for ipa in page.findAll("span", attrs={"class": "IPA"})
                    if ipa.findParent("li") is not None]
        ipas = [self.clean_tag_ipa(ipa_tag) for ipa_tag in ipa_tags]
        ipas = OrderedSet(ipas).items()
        valid_ipas = [ipa for ipa in ipas if self.valid_ipa(ipa)]
        return valid_ipas

    def page_etymologies(self, page, language=None):
        """
        Returns a list of etymological roots on this Wiktionary page
        in this language.

        :param page: BeautifulSoup.Tag, page to find etymology from
        :param language: str, language of etymology
        :return: List[str], etymological roots on this page in this language
        """
        language = self.verify_language(language)
        etym_tags = page.findAll("i", attrs={"xml:lang": self.get_lang_code(language)}, limit=2)
        if len(etym_tags) == 0 and u"+" in page.getText():
            etym_tags = page.findAll("i", attrs={"lang": self.get_lang_code(language)}, limit=2)
        if len(etym_tags) != 2:  # corrects for errors
            etym_tags = list()
        etyms = [self.clean_text(self.remove_superscripts(etym_tag).getText(" ")) for etym_tag in etym_tags]
        return etyms

    # TAG PARSING
    # -----------
    def tag_siblings(self, tag, start_headers=set(), stop_headers=set()):
        """
        Returns the given tag's siblings from start_headers up to stop_headers.

        :param tag: Tag, BeautifulSoup Tag to retrieve children from
        :param start_headers: Set(str), header name(s) to start at
        :param stop_headers: Set(str), header name(s) to stop at
        :return: List[Tag], BeautifulSoup Tag's children up to stop_headers
        """
        curr_tag = tag
        next_sibling = curr_tag.nextSiblingGenerator()
        children = []

        if len(start_headers) != 0:
            while not (getattr(curr_tag, 'name', '') in start_headers):
                try:
                    curr_tag = next(next_sibling)
                except StopIteration:
                    return children

        curr_tag = next(next_sibling)

        if len(stop_headers) != 0:
            while not (getattr(curr_tag, 'name', '') in stop_headers):
                if curr_tag is not None:
                    if str(curr_tag)[:4] == "<!--":
                        break
                    children.append(curr_tag)
                try:
                    curr_tag = next(next_sibling)
                except StopIteration:
                    break

        return children

    def soupify(self, tags):
        """
        Returns a BeautifulSoup page joining each Tag in tags, in rank.

        :param tags: List[Tag], BeautifulSoup Tags to join
        :return: Tag, tags joined into 1 page
        """
        return BeautifulSoup("\n".join([str(tag) for tag in tags]))

    def soupify_siblings(self, tag, start_headers=set(), stop_headers=set()):
        """
        Returns the given tag's siblings as a new tag containing only
        its siblings from (any of) start_headers up to (any of) stop_headers.

        :param tag: Tag, BeautifulSoup Tag to retrieve children from
        :param start_headers: Set(str), header name(s) to start at
        :param stop_headers: Set(str), header name(s) to stop at
        :return: Tag, BeautifulSoup Tag with only this tag's children
        """
        return self.soupify(self.tag_siblings(tag, start_headers, stop_headers))

    # TEXT CLEANUP / HELPERS
    # ----------------------
    def clean_text(self, text):
        """
        Returns the given text in unicode without HTML characters
        and with regular spacing.
        ~
        e.g. clean_text(" hi , how  are you ? ") -> u"hi, how are you?"

        :param text: str, string to clean
        :return: unicode, cleaned unicode string
        """
        return self.clean_spaces(re.sub("&\S{3,10};", " ", self.unicodize(text)))

    def clean_punct(self, text):
        """
        Cleans the spacing around punctuation in the given text.

        :param text: str, text to clean punctuation spacing for
        :return: str, text with clean punctuation spacing
        """
        return text.replace(u" ,", u",").replace(u"( ", u"(").replace(u" )", u")")

    def clean_ipa(self, ipa, scrub=False):
        """
        Returns the given IPA pronunciation with stress marks,
        syllable markers, and parentheses removed.
        ~
        If scrub is True, clean_ipa() also removes given ipa's diacritics.

        :param ipa: unicode, IPA to remove stress/syllable marks from
        :param scrub: bool, whether to also remove diacritics
        :return: unicode, given ipa with stress/syllable marks removed
        """
        cleaned = re.sub(u"[ˈˌ./›\"]", u"", self.clean_word(ipa))
        if scrub:
            cleaned = self.remove_diacritics(cleaned)
        return cleaned

    def clean_tag_ipa(self, tag):
        tag_ipa = self.clean_text(self.remove_superscripts(tag).getText()).replace(" ", "")
        return self.clean_ipa(self.remove_digits(tag_ipa.split(u"→")[0]))

    def clean_word(self, word):
        """
        Returns the given word in lowercase and with punctuation and
        whitespace removed.

        :param word: unicode, word to tag_text
        :return: unicode, cleaned word
        """
        return re.sub("[" + string.punctuation.replace(u"-", u"") + "]", u"", word.lower())

    def clean_header(self, header):
        """
        Returns this Wiktionary header title with [edit]
        stripped from the end.

        :param header: str, Wiktionary header to clean
        :return: str, cleaned Wiktionary header
        """
        return self.clean_text(header).split("[", 1)[0].strip()

    def clean_spaces(self, s):
        """
        Returns s with no more than 1 consecutive space and with
        whitespace stripped from ends.
        ~
        e.g. clean_spaces("  how  are   you  ") -> "how are you"

        :param s: str, string with spaces to tag_text
        :return: str, s cleaned
        """
        return self.clean_punct(self.space_pattern.sub(" ", s)).strip()

    def clean_parentheticals(self, s):
        """
        Returns s with all parentheticals removed.
        ~
        e.g. clean_parentheticals("cat (noun) - animal") -> "cat - animal"

        :param s: str, string to remove parentheticals frosm
        :return: str, s without parentheticals
        """
        last = s
        new = self.paren_pattern.sub(u"", s)
        while last != new:
            last = new
            new = self.paren_pattern.sub(u"", new)
        return new

    def clean_quotes(self, s):
        """
        Returns s with all quotes removed.
        ~
        e.g. clean_parentheticals("cat ("cat")") -> "cat ()"

        :param s: str, string to remove parentheticals from
        :return: str, s without parentheticals
        """
        return self.quote_pattern.sub("", s)

    def ipaize(self, s):
        return u"".join([char for char in s if char in ALLSYMBOLS or char in u", "])

    def remove_digits(self, s):
        return u"".join([char for char in s if not char.isdigit() and char not in u"⁻⁽⁾ˀ"])

    def remove_parens(self, word):
        """
        Returns the given word with parentheses removed.

        :param word: unicode, word to remove parentheses from
        :return: unicode, word with parentheses removed
        """
        return re.sub("\(|\)", "", word)

    def remove_superscripts(self, tag):
        """
        Removes all superscript tags from the given BeautifulSoup Tag.

        :param tag: Tag, BeautifulSoup tag to remove superscripts from
        :return: Tag, tag with superscripts removed
        """
        try:
            tag.sup.decompose()
        except AttributeError:
            pass
        return tag

    def remove_sublists(self, tag):
        """
        Removes all sublist tags (i.e., ul and dl) from the given BeautifulSoup Tag.

        :param tag: Tag, BeautifulSoup tag to remove sublists from
        :return: Tag, tag with sublists removed
        """
        self.remove_superscripts(tag)
        try:
            tag.dl.decompose()
        except AttributeError:
            pass
        try:
            tag.ul.decompose()
        except AttributeError:
            pass
        try:
            tag.abbr.decompose()
        except AttributeError:
            pass
        return tag

    def remove_diacritics(self, ipa):
        """
        Returns the given IPA pronunciation with diacritics removed.

        :param ipa: unicode, IPA to remove stress/syllable marks from
        :return: unicode, given ipa with stress/syllable marks removed
        """
        return "".join([c for c in ipa if c not in IPADIACRITICS])

    def unicodize(self, text):
        """
        Returns the given text in unicode.
        ~
        Ensures all text is in unicode for parsing.

        :param text: str, text to decode to unicode
        :return: unicode, text in unicode
        """
        if text is not None:
            if not isinstance(text, unicode):
                text = text.decode("utf-8")
        return text

    def deunicodize(self, text):
        """
        Returns the given text decoded from unicode.
        ~
        Ensures all text is in bytes for printing.

        :param text: unicode, text to encode to bytes
        :return: str, text in bytes
        """
        if text is not None:
            if isinstance(text, unicode):
                text = text.encode("utf-8")
        return text

    def fill_list(self, lst, limit, item=None):
        """
        Adds item to given list until it reaches length limit.

        :param lst: List[X], list to fill with item
        :param limit: int, desired length of list
        :param item: X, item to fill list with
        :return: List[X], original list with item added until limit
        """
        return self.add_item(lst, limit - len(lst), item)

    def add_item(self, lst, times, item=None):
        """
        Adds the given item to the given list the given number of times.
        ~
        e.g. add_item([1,2,3], 2) -> [1,2,3,None,None]

        :param lst: List[X], list to add item to repeatedly
        :param times: int, number of times to add item
        :param item: X, item to add to given lst
        :return: List[X], lst with item added up to times
        """
        lst += [item] * times
        return lst

    def safe_execute(self, default, exception, function, *args):
        """
        Returns the result of the given function with the given arguments.
        If exception is raised, return default.

        :param default: Any, default value to return if exception
        :param exception: Exception, exception to catch
        :param function: function, function to safely execute
        :param args: Any, arguments of given function to execute
        :return: Any, output of given function or default if exception
        """
        try:
            return function(*args)
        except exception:
            return default


class WiktionaryPage:
    """
    A class for parsing Wiktionary pages into language data.
    """
    def __init__(self, word, language=None, parser=None):
        if parser is None:
            self.parser = WiktionaryParser()
        else:
            self.parser = parser
        self.page = self.word_page(word, language)
        self.entries = self.page_entries(self.page, language)

    def word_page(self, word, language):
        """
        Returns a BeautifulSoup Tag corresponding to the Wiktionary
        page for the given word.

        :param word: str, word to retrieve page for
        :return: Tag, BeautifulSoup tag matching given word's page
        """
        language = self.parser.verify_language(language)
        nuwords = [word, word.lower(), word.title()]

        for nuword in nuwords:
            page = self.parser.word_page(nuword)
            if self.parser.valid_page(page, language):
                return page

    def desired_header(self, header):
        return header.split(u"_", 1)[0] in self.parser.HEADER_NAMES

    def page_entries(self, page, language=None):
        """
        Returns all language entries on the given Wiktionary page
        for a word.

        :param page: Tag, HTML Wiktionary page to extract entries from
        :param language: str, language of page entries to retrieve
        :return: dict(str, dict), where str is entry language and dict is...
            key (str) - entry heading
            val (dict) - entry description
        """
        entries = dict()
        if page is None:
            return entries

        entry_headers = {"h3", "h4", "h5"}
        tags = page.findAll("span", attrs={"class": "mw-headline",
                                           "id": lambda i: self.desired_header(i)})

        for tag in tags:
            lang = self.header_lang(tag)
            if lang == "":
                continue
            elif lang[:10] == "Navigation":
                break
            elif language is None or lang == language:
                tag = tag.findParent(entry_headers)
                heading = self.subtag(tag, stop_headers=entry_headers)

                if heading is not None:
                    header_name = self.rename_header(self.header_text(tag))
                    heading_entry = self.heading_entry(heading, header_name, lang)

                    if heading_entry is not None and len(heading_entry) != 0:
                        entries.setdefault(lang, dict())
                        entries[lang].setdefault(header_name, list())
                        subentry = entries[lang][header_name] + heading_entry
                        #print subentry
                        new_entry = OrderedSet(subentry).order_items()
                        entries[lang][header_name] = new_entry

        return entries

    def rename_header(self, header):
        """
        Renames the given header to standardize all inflections
        and conjugations as declensions.

        :param header: str, header to rename if not declension
        :return: str, header renamed if not declension
        """
        return "Declension" if header[:6] == "Inflec" or header[:6] == "Conjug" else header

    def header_text(self, header):
        """
        Returns the given Wiktionary header's text, with
        [edit] stripped from the end.

        :param header: Tag, HTML header to extract text from
        :return: str, Wiktionary header's text
        """
        text = getattr(header, 'text', '')
        return self.parser.clean_header(text)

    def header_lang(self, heading):
        """
        Finds and returns the given Wiktionary heading's
        language.

        :param heading: Tag, HTML tag to find language for
        :return: str, name of heading's language header
        """
        return self.header_text(heading.findPrevious("h2"))

    def subtag(self, tag, start_headers=set(), stop_headers=set()):
        """
        Returns the given Wiktionary HTML Tag as a new Tag
        with contents up to stop_headers.

        :param tag: Tag, HTML to extract new Tag from
        :param start_headers: Set(str), headers to begin new tag at
        :param stop_headers: Set(str), headers to end new tag at
        :return: Tag, this Tag's contents from start_headers up to stop_headers
        """
        if tag is None:
            return
        else:
            return self.parser.soupify_siblings(tag, start_headers, stop_headers)

    def tag_text(self, tag):
        """
        Returns the given Wiktionary HTML tag's text.

        :param tag: Tag, BeautifulSoup tag in HTML containing text
        :return: str, this Tag's text
        """
        if tag is None:
            return
        else:
            return self.parser.clean_text(self.parser.remove_sublists(tag).getText(" "))

    def tag_lemma(self, tag):
        """
        Returns this HTML tag's first lemma, i.e. text
        from span with class=mention or =form-of-definition-link.
        ~
        Used for retrieving lemmas from parts-of-speech definitions.

        :param tag: Tag, BeautifulSoup HTML to extract lemma from
        :return: str, lemma from given tag
        """
        lemma = tag.find("span", attrs={"class": ["mention", "form-of-definition-link"]})
        lemma_text = self.tag_text(lemma)
        return lemma_text

    def pos_tag_definitions(self, pos_tag):
        """
        Returns this part-of-speech tag's definition-lemma pairs,
        with head word as the first item in the list and
        definitions following.
        ~
        e.g. -> [("driven (comparative more driven, superlative most driven)", "driven"),
                 ("Obsessed; passionately motivated to achieve goals.", None),
                 ("(of snow) Formed into snowdrifts by wind.", None)]

             -> [("is", None)
                 ("plural of i", "i"),
                 ("third-person singular present of be", "be")]

        :param pos_tag: Tag, HTML to retrieve pos definitions from
        :return: List[2-tuple], pos_tag's definition-lemma pairs
        """
        pairs = list()
        pos_tag = self.parser.remove_sublists(pos_tag)
        subtags = pos_tag.findAll(["strong", "li"])

        for subtag in subtags:
            defn = self.tag_text(subtag)
            lemma = self.tag_lemma(subtag)
            if defn != "" and lemma != "":
                lemma = None if lemma is None else self.parser.clean_parentheticals(lemma)
                pair = (defn, lemma)
                pairs.append(pair)

        return pairs

    def tag_declension(self, tag, language, simple=False):
        """
        Returns the declension belonging to this tag
        in this language.
        ~
        If simple is set to True, return only a list of words
        corresponding to declension cell values.

        :param tag: Tag, HTML tag containing declension table
        :param language: str, language of tag content
        :param simple: bool, whether tag declension is simple
        :return: dict(str, dict), where str is column name and dict is...
            key (str) - row name
            val (list) - cell values for given column and row
        """
        if tag is not None:
            wikt_table = WiktionaryTable(tag, language, self)

            if simple:
                return wikt_table.get_simple_declension()
            else:
                return wikt_table.get_declension()

    def heading_entry(self, content, header, language):
        """
        Parses a Wiktionary entry from this HTML content
        with this header name and language.

        :param content: Tag, HTML containing entry content
        :param header: str, header name of entry
        :param language: str, language of heading content
        :return: list, parsed entry content
        """
        if header[:4] == "Etym":
            entry = self.parser.page_etymologies(content, language)
        elif header[:6] == "Pronun":
            entry = self.parser.page_ipas(content)
        elif header in self.parser.PARTS_OF_SPEECH:
            entry = self.pos_tag_definitions(content)
        elif header[:6] == "Declen":
            entry = self.tag_declension(content, language, simple=True)
        else:
            entry = list()

        return entry


class WiktionaryTable:
    """
    A class for parsing Wiktionary pages into language data.
    """
    def __init__(self, table, language, wikt_page):
        self.language = language
        self.table = self.tag_table(table, self.language)
        self.wikt_page = wikt_page
        self.rows = self.table_rows(self.table)
        self.num_rows = len(self.rows)
        self.num_cols = self.count_cols(self.table)
        self.declension = None

    def get_simple_declension(self):
        """
        Returns a list of all words in this WiktionaryTable's table.

        :return: List[str], words in this WT's table
        """
        contents = list()
        table_cells = self.table_content(self.table)

        for cell in table_cells:
            contents += self.cell_content(cell)
        return contents

    def get_declension(self):
        """
        Returns a dictionary for the declension from this WiktionaryTable's table.

        :return: dict(str, dict), where str is column name and dict is...
            key (str) - row name
            val (list) - values in cell for column and row
        """
        self.init_declension()
        return self.declension

    def init_declension(self):
        """
        Initializes this WiktionaryTable's declension if not None.

        :return: None
        """
        if self.declension is None:
            self.declension = self.parse_declension(self.table)

    def is_header(self, cell):
        """
        Returns True if the given cell is a (row or column) header,
        False otherwise.

        :param cell: Tag, BeautifulSoup cell in table to check if header
        :return: bool, whether given cell is a (row or column) header
        """
        if cell is not None:
            if cell.name == "th" or cell.name == "td":
                cell_link = cell.find("a")
                if cell_link is None:
                    return True
                else:
                    href = cell_link.get("href")
                    if href is not None:
                        return href[-len(self.language):] != self.language and href[-9:] != "redlink=1"
        return False

    def is_content(self, cell):
        """
        Returns True if the given cell is a cell containing content,
        False otherwise.

        :param cell: Tag, BeautifulSoup cell in table to check if content
        :return: bool, whether given cell contains content
        """
        if cell is not None:
            if cell.name == "td":
                return self.valid_content(cell)
            elif cell.name == "th":
                return self.contains_content(cell)

        return False

    def valid_content(self, cell):
        """
        Returns True if the content in the given cell is valid,
        i.e., not empty, beginning with a superscript, or containing a
        paragraph.

        :param cell: Tag, HTML cell in table to check whether containing valid content
        :return: bool, whether given cell contains valid content
        """
        try:
            first_item = cell.contents[0]
        except (IndexError, AttributeError):
            first_item = cell
        # cell not valid if empty, begins w/ superscript, or has paragraph
        return (not self.is_cell_empty(cell)) and getattr(first_item, 'name', None) != "sup" and cell.find("p") is None

    def contains_content(self, tag):
        """
        Returns True if the given HTML tag contains language content,
        False otherwise.

        :param tag: Tag, BeautifulSoup Tag to ask if it contains content
        :return: bool, True if tag contains content and False otherwise
        """
        tag_link = tag.find("a")
        if tag_link is not None:
            href = tag_link.get("href")
            if href is not None:
                return href[-len(self.language):] == self.language
        return False

    def is_cell_empty(self, cell):
        """
        Returns True if this cell contains no declension data,
        False otherwise.

        :param cell: Tag, BeautifulSoup tag for cell in HTML table
        :return: bool, whether this cell is empty
        """
        if cell is None:
            return True
        else:
            cell_text = cell.getText()
            return cell_text is None or cell_text == u"—"

    def is_col_empty(self, col):
        """
        Returns True if this HTML column is empty and takes up
        a whole row, False otherwise.

        :param col: Tag, BeautifulSoup Tag for column in table
        :return: bool, whether this column is empty
        """
        return self.cell_rowspan(col) >= self.num_rows and col.get("text") is None

    def cell_rowspan(self, cell):
        """
        Returns this BeautifulSoup Tag cell's rowspan.
        ~
        If cell has no rowspan, returns 1.

        :param cell: Tag, BeautifulSoup tag to get rowspan of
        :return: int, rowspan of given cell
        """
        return int(cell.get("rowspan", 1))

    def cell_colspan(self, cell):
        """
        Returns this BeautifulSoup Tag cell's colspan.
        ~
        If cell has no colspan, returns 1.

        :param cell: Tag, BeautifulSoup tag to get colspan of
        :return: int, colspan of this cell
        """
        return int(cell.get("colspan", 1))

    def content_text(self, spans):
        """
        Returns a newline-joined str of text for all content in spans.

        :param spans: List[Tag], HTML tags for content in a cell
        :return: str, text from content in spans
        """
        spans_text = [self.wikt_page.tag_text(span) for span in spans
                      if self.contains_content(span)]
        text = "\n".join(spans_text)
        return text

    def cell_text(self, cell):
        """
        Returns the given cell (from a table)'s text.

        :param cell: Tag, BeautifulSoup tag for cell in HTML table
        :return: str, given cell's text
        """
        try:
            self.wikt_page.parser.remove_sublists(cell)
            spans = cell.findAll("span")

            if len(spans) == 0:
                text = self.wikt_page.tag_text(cell)
            else:
                text = self.content_text(spans)

            return text

        except AttributeError:
            return ""

    def cell_content(self, cell):
        if self.is_content(cell):
            return self.cell_entry(cell)

    def cell_entry(self, cell):
        """
        Returns a list of the words in this cell.

        :param cell: Tag, BeautifulSoup tag for cell in HTML table
        :return: List[str], list of words in this cell
        """
        text = self.cell_text(cell)

        if len(text) != 0:
            delimiters = re.compile("[,/\n]")
            entry = [e.strip() for e in delimiters.split(text)]
            return entry
        else:
            return list()

    def cell_rows(self, coord, table_dict):
        """
        Returns a tuple of the given coordinate
        from the given table_dict's row names.

        :param coord: Tuple(int, int), coordinate to get row names for
        :param table_dict: dict[tuple, Tag], where...
            key (Tuple[int, int]) - table_dict's row and column number
            val (Tag) - cell for row and column
        :return: Tuple(str), given cell's row names
        """
        row_num, col_num = coord
        sorted_dict = sorted(table_dict)
        prev_rows = [c for c in sorted_dict if c[0] == row_num
                     and c[1] < col_num]
        num_rows, num_cols = sorted_dict[-1]
        rows = []
        header_yet = False

        # iterate over previous rows to find closest set of headers
        for row_coord in reversed(prev_rows):
            cell = table_dict[row_coord]
            if self.is_header(cell):
                text = self.cell_text(cell)
                if self.cell_rowspan(cell) <= num_rows and len(text) != 0:
                    if text not in rows:
                        header_yet = True
                        rows.insert(0, text)
            elif header_yet:
                break

        return tuple(rows)

    def cell_cols(self, coord, table_dict):
        """
        Returns a tuple of the given coordinate
        from the given table_dict's column names.

        :param coord: Tuple(int, int), coordinate to get row names for
        :param table_dict: dict[tuple, Tag], where...
            key (Tuple[int, int]) - given table's row and column number
            val (Tag) - cell for given row and column
        :return: Tuple(str), given cell's column names
        """
        row_num, col_num = coord
        sorted_dict = sorted(table_dict)
        prev_cols = [c for c in sorted_dict if c[1] == col_num
                     and c[0] < row_num]
        cols = []
        header_yet = False

        # iterate over previous columns to find closest set of headers
        for col_coord in reversed(prev_cols):
            cell = table_dict[col_coord]
            text = self.cell_text(cell)
            if self.is_header(cell):
                if self.cell_colspan(cell) < self.num_cols and len(text) != 0:
                    header_yet = True
                    cols.insert(0, text)
            elif header_yet:
                break

        return tuple(cols)

    def is_table_declension(self, table, language):
        """
        Returns True if this table is a declension in the given language,
        False otherwise.

        :param table: Tag, Tag, BeautifulSoup tag for HTML table
        :param language: str, language of table
        :return: bool, whether given table is declension
        """
        cells = self.table_content(table)
        links = [cell.find("a") for cell in cells if cell.find("a") is not None]
        hrefs = [link.get("href") for link in links if link.get("href") is not None]
        all_langs = all([href[-len(language):] == language.replace(" ", "_") or
                         href[-9:] == "redlink=1" for href in hrefs])
        return all_langs

    def table_cells(self, table):
        """
        Returns all cells from the given HTML table.

        :param table: Tag, BeautifulSoup tag for an HTML table
        :return: List[Tag], tags for all cells in given table
        """
        return table.findAll(["td", "th"])

    def table_content(self, table):
        """
        Returns all content cells from the given table.

        :param table: Tag, BeautifulSoup tag for an HTML table
        :return: List[Tag], tags for content cells in given table
        """
        return [cell for cell in table.findAll("td") if self.is_content(cell)]

    def table_rows(self, table):
        """
        Returns the given table separated into rows.

        :param table: Tag, BeautifulSoup tag to get rows of
        :return: List[Tag], rows of given table
        """
        try:
            # find hidden rows first
            rows = table.findAll("tr", attrs={"class": "vsHide"})
            if len(rows) != 0:
                return rows
            else:  # if no hidden rows, return all rows
                return table.findAll("tr")
        except AttributeError:
            return list()

    def tag_table(self, tag, language):
        """
        Returns the declensional table for the given HTML
        tag in the given language.

        :param tag: Tag, HTML tag containing declension table
        :return: Tag, declension table from tag in language
        """
        tables = tag.findAll('table')

        for table in tables:
            if self.is_table_declension(table, language):
                return table
        else:
            if len(tables) != 0:
                return tables[0]

        return tag

    def count_cols(self, table):
        """
        Returns the number of columns in the given HTML table.

        :param table: Tag, BeautifulSoup table in HTML from webpage
        :return: int, number of columns in given table
        """
        num_cols = 0
        row1 = table.find("tr")             # 1st row
        try:
            cells = row1.findAll(["th", "td"])  # all headers/cells in 1st row
        except AttributeError:
            return 0

        for cell in cells:
            colspan = self.cell_colspan(cell)
            num_cols += colspan

        return num_cols

    def parse_table(self, table):
        """
        Returns a dictionary representing the given table.

        :param table: Tag, BeautifulSoup tag for an HTML table
        :return: dict[tuple, Tag], where...
            key (tuple[int, int]) - given table's row and column number
            val (Tag) - cell for given row and column
        """
        table_dict = dict()

        if table is not None:
            num_cols = self.num_cols
            row_range = range(self.num_rows)
            row_iter = iter(row_range)

            for r in row_iter:
                row = self.rows[r]
                cells = self.table_cells(row)
                cells_iter = iter(cells)
                col_range = range(num_cols)
                col_iter = iter(col_range)

                for c in col_iter:
                    coord = r, c

                    try:
                        cell = cells_iter.next()
                    except StopIteration:
                        continue
                    else:
                        # skip empty columns
                        while self.is_col_empty(cell):
                            try:
                                cell = cells_iter.next()
                            except StopIteration:
                                break

                        if self.is_col_empty(cell):
                            col_range = col_range[:-1]
                            num_cols -= 1
                            continue

                    while coord in table_dict:
                        try:
                            col_iter.next()
                            c += 1
                        except StopIteration:
                            try:
                                row_iter.next()
                                r += 1
                            except StopIteration:
                                break

                        coord = r, c
                    else:
                        rowspan = self.cell_rowspan(cell)
                        colspan = self.cell_colspan(cell)
                        rowspan = min(rowspan, self.num_rows)
                        colspan = min(colspan, num_cols)

                        if colspan != 1 or rowspan != 1:
                            rs = 0

                            while rs < rowspan:
                                coord = r + rs, c
                                table_dict[coord] = cell
                                cs = 1

                                while cs < colspan:
                                    coord = r + rs, c + cs
                                    table_dict[coord] = cell
                                    cs += 1
                                rs += 1

                            for i in range(1, colspan):
                                try:
                                    col_iter.next()
                                except StopIteration:
                                    break

                            continue
                        else:
                            table_dict[coord] = cell

        return table_dict

    def parse_declension(self, table):
        """
        Returns a declension dictionary for the given table.
        ~
        If table has multiple columns or rows, this method adds
        all column/row names in a tuple.

        :param table: Tag, BeautifulSoup table
        :return: dict(str, dict), where...
            key (str) - declension column (i.e., plural or sing.)
            val (dict[str, list]) - declension row (e.g., nominative) &
                list of words for given row & column
        """
        coords = self.parse_table(table)
        sorted_coords = sorted(coords)
        declension = dict()
        line_text = lambda line: " > ".join([l.lower().replace(" ", "_") for l in line
                                             if len(line) > 0 and u"—" not in l])

        for coord in sorted_coords:
            cell = coords[coord]
            if self.is_content(cell) and self.cell_colspan(cell) <= self.num_cols:
                row = self.cell_rows(coord, coords)
                col = self.cell_cols(coord, coords)
                row_text = line_text(row)
                col_text = line_text(col)
                entry = self.cell_entry(cell)
                if len(entry) > 0 and len(col_text) > 0:
                    if len(row_text) > 0 or self.num_rows-self.num_cols == 1:
                        declension.setdefault(col_text, dict())
                        new_entry = declension[col_text].setdefault(row_text, list())
                        new_entry += entry
                        new_entry = OrderedSet(new_entry).items()
                        declension[col_text][row_text] = new_entry

        return declension

    def print_declension(self, declension):
        """
        Prints given declension and returns None.

        :param declension: dict, declension to print
        :return: None
        """
        for d in sorted(declension):
            value = declension[d]
            print d, ":"

            for val in sorted(value):
                print "\t", val
                v = value[val]
                print "\t\t", "\n\t\t".join(v)

    def visualize_declension(self, declension):
        """
        Prints the given declension to the user as a table.

        :param declension: dict[tuple], row-col int keys with cell values
        :return: None
        """
        if len(declension) != 0:
            bold = '\033[1m'
            end_bold = '\033[0m'

            declension_len = len(max(declension.values(), key=lambda v: len(v.text)).text)
            max_row, max_col = sorted(declension)[-1]
            row_digits = len(str(max_row))

            col_width = declension_len + 5
            col_intro = " "*int(col_width * 1.25)
            col_space = " "*col_width

            print "Declension:\n"
            print bold + col_intro + col_space.join([str(i) for i in range(max_col + 1)]) + end_bold

            for coord in sorted(declension):
                x, y = coord
                val = declension[coord]
                text = self.wikt_page.parser.clean_text(val.getText(" "))
                offset = col_width - len(text)
                if y == 0:
                    print
                    print bold + str(coord[0]).zfill(row_digits) + end_bold + col_space,

                is_header = self.is_header(val)
                if is_header:
                    text = bold + text + end_bold
                print text + (" " * offset),
            print

