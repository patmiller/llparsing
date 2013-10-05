llparsing
=========

A simple Python metaclass that creates small languages (including token parsing) without a lex/yacc or flex/bison like step.  Each method describes a production.  The arguments provide leaves to each node.  The return value returns the node.
