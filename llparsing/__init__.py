"""A recursive descent base class to autogenerate parser objects

Inheriting this as a base class lets you quickly build LL class
recursive descent parsers with no flex/bison like step.  I think
this is a huge improvement over two-step methods since you can
build a tiny grammar and actions all in one step.
"""

from lexer import Lexer,Token
from parser import ParserType,Parser,\
    sequence,\
    WhiteSpace,PoundComment,CComment,CxxComment
from grammar import Grammar
from util import AmbiguityError


