from miasm2.ir.translators.translator import Translator
from miasm2.core import asmbloc
from miasm2.expression.modint import size2mask


class TranslatorC(Translator):
    "Translate a Miasm expression to an equivalent C code"

    # Implemented language
    __LANG__ = "C"

    # Operations translation
    dct_shift = {'a>>': "right_arith",
                 '>>': "right_logic",
                 '<<': "left_logic",
                 'a<<': "left_logic",
                 }
    dct_rot = {'<<<': 'rot_left',
               '>>>': 'rot_right',
               }
    dct_div = {'div8': "div_op",
               'div16': "div_op",
               'div32': "div_op",
               'idiv32': "div_op",  # XXX to test
               '<<<c_rez': 'rcl_rez_op',
               '<<<c_cf': 'rcl_cf_op',
               '>>>c_rez': 'rcr_rez_op',
               '>>>c_cf': 'rcr_cf_op',
               }


    def from_ExprId(self, expr):
        if isinstance(expr.name, asmbloc.asm_label):
            return "0x%x" % expr.name.offset
        return str(expr)

    def from_ExprInt(self, expr):
        return "0x%x" % expr.arg.arg

    def from_ExprAff(self, expr):
        return "%s = %s" % tuple(map(self.from_expr, (expr.dst, expr.src)))

    def from_ExprCond(self, expr):
        return "(%s?%s:%s)" % tuple(map(self.from_expr,
                                        (expr.cond, expr.src1, expr.src2)))

    def from_ExprMem(self, expr):
        return "MEM_LOOKUP_%.2d(vm_mngr, %s)" % (expr.size,
                                                 self.from_expr(expr.arg))

    def from_ExprOp(self, expr):
        if len(expr.args) == 1:
            if expr.op == 'parity':
                return "parity(%s&0x%x)" % (self.from_expr(expr.args[0]),
                                            size2mask(expr.args[0].size))
            elif expr.op in ['bsr', 'bsf']:
                return "x86_%s(%s, 0x%x)" % (expr.op,
                                             self.from_expr(expr.args[0]),
                                             expr.args[0].size)
            elif expr.op == '!':
                return "(~ %s)&0x%x" % (self.from_expr(expr.args[0]),
                                        size2mask(expr.args[0].size))
            elif expr.op in ["hex2bcd", "bcd2hex"]:
                return "%s_%d(%s)" % (expr.op, expr.args[0].size,
                                      self.from_expr(expr.args[0]))
            elif (expr.op.startswith("double_to_") or
                  expr.op.endswith("_to_double")   or
                  expr.op.startswith("access_")    or
                  expr.op.startswith("load_")      or
                  expr.op in ["-", "ftan", "frndint", "f2xm1",
                              "fsin", "fsqrt", "fabs", "fcos"]):
                return "%s(%s)" % (expr.op, self.from_expr(expr.args[0]))
            else:
                raise NotImplementedError('Unknown op: %r' % expr.op)

        elif len(expr.args) == 2:
            if expr.op == "==":
                return '(((%s&0x%x) == (%s&0x%x))?1:0)' % (
                    self.from_expr(expr.args[0]), size2mask(expr.args[0].size),
                    self.from_expr(expr.args[1]), size2mask(expr.args[1].size))
            elif expr.op in self.dct_shift:
                return 'shift_%s_%.2d(%s , %s)' % (self.dct_shift[expr.op],
                                                   expr.args[0].size,
                                                   self.from_expr(expr.args[0]),
                                                   self.from_expr(expr.args[1]))
            elif expr.is_associative() or expr.op in ["%", "/"]:
                oper = ['(%s&0x%x)' % (self.from_expr(arg), size2mask(arg.size))
                        for arg in expr.args]
                oper = str(expr.op).join(oper)
                return "((%s)&0x%x)" % (oper, size2mask(expr.args[0].size))
            elif expr.op in ['-']:
                return '(((%s&0x%x) %s (%s&0x%x))&0x%x)' % (
                    self.from_expr(expr.args[0]), size2mask(expr.args[0].size),
                    str(expr.op),
                    self.from_expr(expr.args[1]), size2mask(expr.args[1].size),
                    size2mask(expr.args[0].size))
            elif expr.op in self.dct_rot:
                return '(%s(%s, %s, %s) &0x%x)' % (self.dct_rot[expr.op],
                                                   expr.args[0].size,
                                                   self.from_expr(expr.args[0]),
                                                   self.from_expr(expr.args[1]),
                                                   size2mask(expr.args[0].size))
            elif (expr.op.startswith('cpuid') or
                  expr.op.startswith("fcom")  or
                  expr.op in ["fadd", "fsub", "fdiv", 'fmul', "fscale"]):
                return "%s(%s, %s)" % (expr.op, self.from_expr(expr.args[0]),
                                       self.from_expr(expr.args[1]))
            elif expr.op == "segm":
                return "segm2addr(vmcpu, %s, %s)" % (
                    self.from_expr(expr.args[0]), self.from_expr(expr.args[1]))
            elif expr.op in ['udiv', 'umod', 'idiv', 'imod']:
                return '%s%d(vmcpu, %s, %s)' % (expr.op,
                                                expr.args[0].size,
                                                self.from_expr(expr.args[0]),
                                                self.from_expr(expr.args[1]))
            elif expr.op in ["bcdadd", "bcdadd_cf"]:
                return "%s_%d(%s, %s)" % (expr.op, expr.args[0].size,
                                          self.from_expr(expr.args[0]),
                                          self.from_expr(expr.args[1]))
            else:
                raise NotImplementedError('Unknown op: %r' % expr.op)

        elif len(expr.args) == 3 and expr.op in self.dct_div:
            return '(%s(%s, %s, %s, %s) &0x%x)' % (self.dct_div[expr.op],
                                                   expr.args[0].size,
                                                   self.from_expr(expr.args[0]),
                                                   self.from_expr(expr.args[1]),
                                                   self.from_expr(expr.args[2]),
                                                   size2mask(expr.args[0].size))

        elif len(expr.args) >= 3 and expr.is_associative():  # ?????
            oper = ['(%s&0x%x)' % (self.from_expr(arg), size2mask(arg.size))
                    for arg in expr.args]
            oper = str(expr.op).join(oper)
            return "((%s)&0x%x)" % (oper, size2mask(expr.args[0].size))

        else:
            raise NotImplementedError('Unknown op: %s' % expr.op)

    def from_ExprSlice(self, expr):
        # XXX check mask for 64 bit & 32 bit compat
        return "((%s>>%d) & 0x%X)" % (self.from_expr(expr.arg),
                                      expr.start,
                                      (1 << (expr.stop - expr.start)) - 1)

    def from_ExprCompose(self, expr):
        out = []
        # XXX check mask for 64 bit & 32 bit compat
        dst_cast = "uint%d_t" % expr.size
        for x in expr.args:
            out.append("(((%s)(%s & 0x%X)) << %d)" % (dst_cast,
                                                      self.from_expr(x[0]),
                                                      (1 << (x[2] - x[1])) - 1,
                                                      x[1]))
        out = ' | '.join(out)
        return '(' + out + ')'


# Register the class
Translator.register(TranslatorC)
