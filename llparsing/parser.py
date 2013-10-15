import re,types
from grammar import Grammar
from lexer import Lexer

class template(object):
    def __init__(self,f):
        self.function = f
        return

    def updates(self):
        return {}

def set_arguments(f,args,fname=None):
    co = f.func_code
    nargs = len(args)
    if nargs > co.co_argcount: raise RuntimeError('replacing too many args')
    
    newcode = types.CodeType(
        nargs,
        co.co_nlocals,
        co.co_stacksize,
        co.co_flags,
        co.co_code,
        co.co_consts,
        co.co_names,
        args+co.co_varnames[nargs:],
        co.co_filename,
        fname or f.func_name,
        co.co_firstlineno,
        co.co_lnotab,
        co.co_freevars,
        co.co_cellvars)
    newfunc = types.FunctionType(
        newcode,
        f.func_globals,
        fname or f.func_name,
        f.func_defaults,
        f.func_closure)
    for k,v in f.func_dict:
        if k not in newfunc.func_dict:
          newfunc.func_dict[k] = v
    return newfunc

class sequence(template):
    def updates(self):
        # The function should look list foolist(foo,sep)
        # or foolist(foo)

        # We need three new functions (productions) to build the list
        # so if we start with
        #   def foos(self,foo,sep): ...
        # we really want
        #   foos       -> foos_body
        #   foos_body  -> foo foos_tail
        #   foos_tail  -> sep foos
        #   foos_tail_ -> 

        co = self.function.func_code
        fname = self.function.func_name
        args = co.co_varnames[1:self.function.func_code.co_argcount]

        def main_function(self,element,tail):
            tail.insert(0,element)
            return tail
        def tail_function_(self):
            return []

        if len(args) == 1:
            element = args[0]
            sep = None
        elif len(args) == 2:
            element,sep = args
        else:
            raise RuntimeError('Invalid arg count for @sequence (1 or 2)')

        main = fname+'_body'
        tail = fname+'_tail'
        tail_ = fname+'_tail_'

        main_function = set_arguments(main_function,('self',element,tail),main)
        tail_function_ = set_arguments(tail_function_,('self',),tail_)

        if sep is None:
            def tail_function(self,main):
                return main
            tail_function = set_arguments(tail_function,('self',main),tail)
        else:
            def tail_function(self,sep,main):
                return main
            tail_function = set_arguments(tail_function,('self',sep,main),tail)

        # Rebuild the functions with patched names
        fprime = set_arguments(self.function,('self',main))

        # We will expand to a few functions
        result = {
            fname : fprime,
            main : main_function,
            tail : tail_function,
            tail_ : tail_function_,
            }

        return result

def stem(s):
    while s:
        if s[-1] not in '012345678_': break
        s = s[:-1]
    return s

def method_as_rule(m):
    co = m.im_func.func_code
    non_self_args = co.co_varnames[1:co.co_argcount]
    return stem(m.__name__),map(stem,non_self_args)

def find_methods(T,key):
    import types
    candidates = [getattr(T,name) for name in dir(T) if stem(name) == key]
    return [m for m in candidates if isinstance(m,types.MethodType)]

class ParserType(type):
    def __new__(meta,name,bases,dct):
        # We may have some templates in the dictionary...
        # Expand those now
        for k,v in dct.items():
            if isinstance(v,template):
                del dct[k]
                dct.update(v.updates())

        # Build a type that we use to find methods in a consistent
        # way
        T = super(ParserType,meta).__new__(meta,name,bases,dct)


        # We start with a rule for the start symbol and try to
        # add any other non-terminal rule we can find. If there
        # is no start symbol, this is just a base class so there
        # is no parser to build
        start_symbol = dct.get('__start__','start')
        starts = find_methods(T,start_symbol)
        if not starts: return T

        # If the start is ambiguous, give up
        if len(starts) > 1:
            raise AmbiguityError('multiple start symbols: {0}'.format(
                    ' '.join(x.__name__ for x in starts)))

        # See what rules we can reach from the start symbol
        # the rhs contains both terminals and non-terminals.
        # It's a NT if there is a stemmed method that matches
        # otherwise it is a terminal.
        start = starts[0]
        NT = set()
        start_rule = method_as_rule(start)
        start_rhs = start_rule[1]
        if not start_rhs:
            raise AmbiguityError('start rule has an empty rhs')
        eof = start_rhs[-1]
        if find_methods(T,eof):
            raise AmbiguityError('start rule must end with an eof terminal symbol')
        rules = []
        actions = []
        labels = []
        work = [start_symbol]
        while work:
            sym = work.pop()

            # If we saw this before, don't bother to do it again
            if sym in NT: continue
        
            # If we have no stemmed methods, it is a terminal
            methods = find_methods(T,sym)
            if not methods: continue

            # symbol must be a non-terminal
            NT.add(sym)

            # Add each method as a rule
            for m in methods:
                r = method_as_rule(m)
                work += r[1][:]
                actions.append((m,r[1]))
                labels.append(m.__name__)
                rules.append(r)

        # We pull some info from the grammar we generate
        G = Grammar(rules,start_symbol,actions,labels)
        dct['__grammar__'] = G
        dct['__predict_table__'] = G.predict
        dct['__terminals__'] = G.T
        dct['__non_terminals__'] = G.NT

        # Add in generated default parser and lexer if needed
        if '__parse__' not in dct:
            def __parse__(self,*args,**kwargs):
                stream = iter(self.__lexer__(*args,**kwargs))
                self.__current_token__ = next(stream)
                return self.__predict__(start_symbol,stream)
            dct['__parse__'] = __parse__

        if '__lexer__' not in dct:
            dct['__lexer__'] = __lexer__ = Lexer(G.T,T,eof)


        def __predict__(self,symbol,stream):
            # Predicting tokens is easy, see if it matches
            if symbol in self.__terminals__:
                token = self.__current_token__
                if token.flavor != symbol:
                    raise SyntaxError('{0}:{1}: expected {2}, got {3}\n'.format(
                            token.filename,
                            token.lineno,
                            symbol,
                            token.flavor)
                                      + str(token))
                self.__current_token__ = next(stream)
                return token

            # For non-terminals, we go to the table
            predictions = self.__predict_table__[symbol]
            prediction = predictions.get(self.__current_token__.flavor)
            if prediction is None:
                raise SyntaxError('{0}:{1}: for {2}, expected {3}, got {4}\n'.format(
                        self.__current_token__.filename,
                        self.__current_token__.lineno,
                        symbol,
                        ' or '.join(predictions.keys()),
                        self.__current_token__.flavor)
                                  + str(self.__current_token__))
            action,requires = prediction
            # We unwind much of the predict(predict(predict(...))) here
            # for readability
            try:
                args = [self.__predict__(sym,stream) for sym in requires]
            except SyntaxError,syntax_error:
                raise syntax_error
                
            return action(self,*args)
        dct['__predict__'] = __predict__

        # We need to patch the predict table so that we use result's
        # unbound methods, not the trial type's methods
        result = super(ParserType,meta).__new__(meta,name,bases,dct)
        for sym,predictions in result.__predict_table__.iteritems():
            for terminal,(badmethod,args) in predictions.items():
                goodmethod = getattr(result,badmethod.__name__)
                predictions[terminal] = (goodmethod,args)
        return result

class Parser(object):
    __metaclass__ = ParserType

class WhiteSpace(object):
    ignore_whitespace = re.compile(r'[ \t\n]')

class PoundComment(object):
    ignore_poundcomment = re.compile(r'#.*')

class CComment(object):
    ignore_ccoment = re.compile(r'\/\*.*\*\/',re.DOTALL)

class CxxComment(CComment):
    ignore_cxxcoment = re.compile(r'//.*')

