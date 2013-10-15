import re
from util import AmbiguityError

class Token:
    """A simple token class

    A token has a flavor (the name of the token type), a value (the
    text of the token), and some line information."""

    def __init__(self,value,flavor,offset,filename,lineno,column,line):
        self.value = value
        self.flavor = flavor
        self.offset = offset
        self.filename = filename
        self.lineno = lineno
        self.column = column
        self.line = line
        return

    def __str__(self):
        return self.line + '\n' + '-'*self.column + '^\n'

    def __repr__(self):
        return repr((self.value,self.flavor))

class Lexer:
    def __init__(self,terminals,source,eofsym):
        self.eofsym = eofsym
        missing = object()
        name2pattern = {}
        for sym in terminals:
            # We don't match a pattern for this one
            if sym == eofsym: continue

            # If we provide a token description in our class,
            # then we use it (either a regex or a exact match)
            regex = getattr(source,sym,missing)
            if regex is not missing:
                if not isinstance(regex,str):
                    name2pattern[sym] = regex
                else:
                    name2pattern[sym] = re.compile(re.escape(regex))
                continue

            # OK... we need to intuit what the user wanted
            # _ ==> ''  (fix with explicit attribute name in class)
            # __ ==> '' (ditto)
            # foo ==> 'foo'
            # else_ ==> 'else'
            # else_3 ==> 'else'
            # _3 ==> 3
            # _0123 ==> chr(0123)
            
            if sym.startswith('_'):
                if len(sym) == 2:
                    name2pattern[sym] = sym[1]
                elif sym.startswith('_0'):
                    try:
                        name2pattern[sym] = re.compile(chr(int(sym[1:],8)))
                    except ValueError:
                        name2pattern[sym] = re.compile(re.escape(sym))
                else:
                    name2pattern[sym] = re.compile(re.escape(sym))
            else:
                s = sym
                while s:
                    if s[-1] not in '012345678_': break
                    s = s[:-1]
                name2pattern[sym] = re.compile(re.escape(s))

        # We may have some comments and whitespace things to ignore...
        for k in dir(source):
            if k.startswith('ignore'):
                v = getattr(source,k)
                if isinstance(v,str):
                    name2pattern[k] = re.compile(v)
                else:
                    name2pattern[k] = v

        # Some of our patterns are simple keywords which we prefer
        # over other matches
        import string
        keyword_char_set = set(string.letters+string.digits+'_')
        self.keywords = set( flavor for flavor,v in name2pattern.iteritems()
                             if all((character in keyword_char_set)
                                    for character in v.pattern) )

        self.patterns = name2pattern
        return

    def __call__(self,source,*args,**kwargs):
        self.filename = getattr(source,'name','<string>')
        read = getattr(source,'read',None)
        # TODO: try mmap interface
        if read is not None:
            source = source.read()
        offset = 0
        self.lineno = 1

        patterns = self.patterns
        match = re.match
        values = patterns.values()
        keys = patterns.keys()
        while 1:
            # We jump to the current point
            buf = buffer(source,offset)

            # Apply all the regex
            matches = [match(value,buf) for value in values]

            # Pick only matches that succeed
            good_matches = [(m.group(),key) for m,key in zip(matches,keys)
                            if m is not None]

            # No match is OK on end-of-string
            if not good_matches:
                if buf:
                    m = buf[0]
                    flavor = '_%03o'%ord(m)  # Name is octal name
                else:
                    m = ''
                    flavor = self.eofsym

            # Normally, we'll only have one match, return it
            elif len(good_matches) == 1:
                m,flavor = good_matches[0]

            # Best match is the longest token
            else:
                def key(x):
                    return len(x[0])
                best_matches = sorted(good_matches,key=key)

                # We pick the longest match.  It is ambiguous if any
                # matches are the same length (unless one is a keyword)
                longest_matches = [x for x in best_matches
                                   if len(x[0]) == len(best_matches[0][0])]

                # If we have exactly one keyword match, we return that
                keyword_matches = [(m,flavor) for m,flavor in longest_matches
                                   if flavor in self.keywords]
                if len(keyword_matches) == 1:
                    m,flavor = keyword_matches[0]
                elif len(longest_matches) > 1:
                    raise AmbiguityError('Token {0} is one of {1}\n'.format(
                            matches[0][0],
                            '|'.join(x[1] for x in matches)
                            ))
                else:
                    m,flavor = longest_matches[0]

            # We build our token...
            start_line = source.rfind('\n',0,offset)+1
            end_line = source.find('\n',start_line)
            if end_line == -1: end_line = len(source)
            column = offset-start_line
            token = Token(m,flavor,offset,self.filename,self.lineno,column,source[start_line:end_line].expandtabs())

            # and update the positions
            self.lineno += m.count('\n')
            offset += len(m)

            # We ignore some tokens, and finish with an EOF
            if flavor.startswith('ignore'): continue
            yield token
            if flavor == self.eofsym: break

        # We keep yielding EOF forever
        while 1:
            yield token
        return
