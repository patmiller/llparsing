llparsing
=========

Copyright (c) 2013 by Pat Miller

This work is made available under the terms of the Creative Commons
Attribution-ShareAlike 3.0 license, http://creativecommons.org/licenses/by-sa/3.0/

A simple Python metaclass that creates small languages (including token parsing)
without a lex/yacc or flex/bison like step.  Each method describes a production.
The arguments provide leaves to each node.  The return value returns the node.

This is guilt-ware.

If you think this code saves you money (remember, time is money!),
I will happily take PayPal donations to cover beer, pizza,
my kids' college tuition, or a small airplane (please specify).

Don't use this in mission critical software without enough
testing to make sure you think it's safe.  This depends on
some possibly fragile assumptions, so it can give you unexpected
results. YMMV.

User assumes all risk.

I'm fine with any use of this, commercial or otherwise.  Give me
credit though!

Pat Miller -- patrick.miller@gmail.com
