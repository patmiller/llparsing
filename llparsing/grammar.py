"""Create grammar objects to build LL predict tables
"""

from util import AmbiguityError

class Grammar:
    """A helper class to derive the LL predict table from a set of rules.

    We think about a grammar as something like
    G = { rules in NT -> NT|T* }

    S -> E $
    E -> T ETail
    ETail -> + ETail
    ETail ->
    T -> id

    Here, the non-terminals NT are
    NT = { S E ETail T }

    and terminals T are
    T = { + id }
    """

    def __init__(self,rules,start='S',actions=None,labels=None):
        self.__rules = rules
        self.__start = start
        self.__actions = actions or range(len(rules))
        self.__labels = labels or [str(a) for a in self.__actions]
        return

    @property
    def rules(self):
        "The collection of lhs-> (NT|T)*"
        return self.__rules

    @property
    def start(self):
        "The start symbol"
        return self.__start

    @property
    def NT(self):
        "The set of non-terminal symbols"
        try: return self.__NT
        except AttributeError: pass

        self.__NT = set(lhs for lhs,_ in self.rules)
        return self.__NT

    @property
    def T(self):
        "The set of terminal symbols"
        try: return self.__T
        except AttributeError: pass

        # Any symbol on the rhs that is not a non-terminal!
        NT = self.NT
        RHS = set(sum((rhs for lhs,rhs in self.rules),[]))
        self.__T = RHS.difference(NT)
        return self.__T

    @property
    def vocabulary(self):
        "All symbols in NT union T"
        return self.NT.union(self.T)

    @property
    def derives_lambda(self):
        "The set { NT | NT -*-> empty }, that is NT that can derive the empty string"
        try: return self.__derives_lambda
        except AttributeError: pass

        derives_lambda = set()

        # We keep sweeping through the rules so long as we find updates
        changed = True
        while changed:
            changed = False
            for lhs,rhs in self.rules:
                rhs_derives_lambda = True
                for sym in rhs:
                    rhs_derives_lambda = rhs_derives_lambda and sym in derives_lambda
                if rhs_derives_lambda and lhs not in derives_lambda:
                    changed = True
                    derives_lambda.add(lhs)
        
        self.__derives_lambda = derives_lambda
        return self.__derives_lambda

    def __compute_first(self,first,rhs):
        # Empty rhs have a first set of just lambda
        k = len(rhs)
        if not k: return set([None])

        # Start with the first of the 1st symbol
        result = set(filter(None,first[rhs[0]]))
        i = 0
        while i < k-1 and None in first[rhs[i]]:
            i += 1
            for sym in first[rhs[i]]:
                if sym is not None: result.add(sym)
        if i == k-1 and None in first[rhs[i]]:
            result.add(None)
        return result

    @property
    def first(self):
        "A dictionary of the first sets for each NT"
        try: return self.__first
        except AttributeError: pass

        # Initialize the first sets of those things that can derive
        # lambda to the set([lambda]), the rest to nothing
        derives_lambda = self.derives_lambda
        self.__first = first = {}

        for sym in self.NT:
            first[sym] = set([None]) if sym in derives_lambda else set()

        # The "first" of a terminal, is of course, the terminal.  The
        # first of any LHS that starts with the terminal, of course
        # also contains that terminal.
        for sym in self.T:
            first[sym] = [sym]
            for lhs,rhs in self.rules:
                if rhs and rhs[0] == sym:
                    first[lhs].add(sym)

        # Now we form the closure to account for NT that can derive lambda
        changed = True
        while changed:
            changed = False

            for lhs,rhs in self.rules:
                rhs_first = self.__compute_first(first,rhs)
                for sym in rhs_first:
                    if sym not in first[lhs]:
                        first[lhs].add(sym)
                        changed = True
        return first

    @property
    def follow(self):
        "A dictionary of follow sets for each NT"
        try: return self.__follow
        except AttributeError: pass

        # We start with empty follow sets for all NT except
        # the start symbol which can be followed by lambda
        NT = self.NT
        self.__follow = follow = dict( (sym,set()) for sym in NT )
        follow[self.start] = None

        # Form the closure of follows
        changed = True
        rules = self.rules
        first = self.first
        while changed:
            changed = False

            for lhs,rhs in rules:
                for i,B in enumerate(rhs):
                    if B in NT:
                        y = rhs[i+1:]
                        y_first = self.__compute_first(first,y)
                        for sym in y_first:
                            if sym is not None and sym not in follow[B]:
                                follow[B].add(sym)
                                changed = True
                        if None in y_first:
                            for sym in follow[lhs] or ():
                                if sym not in follow[B]:
                                    follow[B].add(sym)
                                    changed = True

        return follow

    @property
    def predict(self):
        "The predict table for each NT"
        try: return self.__predict
        except AttributeError: pass

        # We start with empty predict tables for each NT
        self.__predict = predict = dict( (sym,{}) for sym in self.NT )

        # Now we fill in from the rules
        first = self.first
        follow = self.follow
        actions = self.__actions or range(len(self.rules))
        for i,(lhs,rhs) in enumerate(self.rules):
            first_i = self.__compute_first(first,rhs)
            if None in first_i:
                predict_i = follow[lhs].union(filter(None,first_i))
            else:
                predict_i = first_i
            for sym in predict_i:
                if sym in predict[lhs]:
                    error_msg = 'In rule {i}, "{rule}" {sym} already predicts "{prediction}" for {lhs}'.format(
                        i=i,
                        rule=self.__rule_string(self.rules[i]),
                        sym=sym,
                        prediction=self.__rule_string(self.rules[predict[lhs][sym]]),
                        lhs=lhs,
                        )
                    raise AmbiguityError(error_msg)
                predict[lhs][sym] = actions[i]
        
        return predict

    def __rule_string(self,rule):
        lhs,rhs = rule
        return '{0} -> {1}'.format(lhs,' '.join(rhs))

    def ll_table(self):
        "A compact human-readable representation of the ll predict table"
        from cStringIO import StringIO
        out = StringIO()
        predicts = self.predict

        def representation(action):
            for a,r in zip(self.__actions,self.__labels):
                if a is action: return r
            return str(action)

        # some width info
        T = self.T
        NT = self.NT
        colwidth = max(len(x) for x in T)+2
        symwidth = max(len(x) for x in NT)+1
        for sym,pdict in predicts.iteritems():
            for action in pdict.values():
                r = representation(action)
                colwidth = max(len(r)+2,colwidth)

        # Terminal set labels the columns
        T = self.T
        header = ' '*symwidth + '|'+ '|'.join(x.center(colwidth) for x in T)
        print >>out,header
        print >>out,'-'*symwidth + ('+' + '-'*colwidth)*len(T)

        # Non-terminals each have a prediction for a rule
        predict = self.predict
        for A in self.NT:
            out.write(A.ljust(symwidth))
            for sym in T:
                out.write('|')
                if sym in predict[A]:
                    action = predict[A][sym]
                    r = representation(action)
                    out.write(r.center(colwidth))
                else:
                    out.write(' '*colwidth)
            out.write('\n')

        return out.getvalue()

    def __repr__(self):
        from cStringIO import StringIO
        out = StringIO()
        print >>out,'T:',' '.join(self.T)
        print >>out,'NT:',' '.join(self.NT)
        for i,(lhs,rhs) in enumerate(self.rules):
            print >>out,'[%d]'%i,lhs,'=>',' '.join(rhs)
        return out.getvalue()
                    

        


    
