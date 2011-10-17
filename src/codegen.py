from amqp_codegen import *

def sanitizeName(specName):
    if specName == 'delete':
        specName = 'delete_'
    if specName == 'return':
        specName = 'return_'
    res = specName.replace('-', '_')
    res = res.replace(' ', '_')
    return res

types = {
       'octet':'uint8_t',
       'short':'uint16_t',
       'long':'uint32_t',
       'longlong':'uint64_t',
       'shortstr':'std::string',
       'longstr':'std::string',
       'bit':'bool',
       'table':'table',
       'timestamp':'uint64_t'
       }



def genHeader(spec):

    def genConstants():
        print "enum frame_constants"
        print "{"
        for c in spec.constants:
            name, value, klass = c
            if klass == '' and name.startswith('FRAME'):
                print "  %s = %s," % (sanitizeName(name), value)
        print "};"
        print ""
        print "enum soft_errors"
        print "{"
        for c in spec.constants:
            name, value, klass = c
            if klass == 'soft-error':
                print "  %s = %s," % (sanitizeName(name), value)
        print "};"
        print ""
        print "enum hard_errors"
        print "{"
        for c in spec.constants:
            name, value, klass = c
            if klass == 'hard-error':
                print "  %s = %s," % (sanitizeName(name), value)
        print "};"


    def genGetter(field):
        amqp_type = spec.resolveDomain(field.domain)
        name = sanitizeName(field.name)
        if (amqp_type == 'table'):
            print "    inline table& get_%s() { return m_%s; }" % (name, name)
            print "    inline const table& get_%s() const { return m_%s; }" % (name, name)
        else:
            type = types[amqp_type]
            print "    inline %s get_%s() const { return m_%s; }" % (type, name, name)

    def genSetter(field):
        amqp_type = spec.resolveDomain(field.domain)
        name = sanitizeName(field.name)
        if (amqp_type == 'table'):
            pass
        elif (amqp_type == 'shortstr'):
            print "    inline void set_%s(const std::string& s) { detail::validate_shortstring(s); m_%s = s; }" % (name, name)
        elif (amqp_type == 'longstr'):
            print "    inline void set_%s(const std::string& s) { detail::validate_longstring(s); m_%s = s; }" % (name, name)
        else:
            type = types[amqp_type]
            print "    inline void set_%s(%s v) { m_%s = v; }" % (name, type, name)

    print """// Autogenerated code. Do not edit. Edit codegen.py instead

#ifndef _LIBAMQPP_METHODS_GEN_H_INCLUDED_
#define _LIBAMQPP_METHODS_GEN_H_INCLUDED_

#include "export.h"
#include "detail/methods.h"
#include "detail/string_utils.h"
#include "table.h"

#include <boost/cstdint.hpp>
#include <boost/make_shared.hpp>
#include <boost/shared_ptr.hpp>

#include <iosfwd>
#include <string>

#ifdef _MSC_VER
# pragma warning ( push )
# pragma warning ( disable: 4251 )
#endif
namespace amqpp
{
namespace detail
{
"""
    genConstants()
    print """}
namespace methods
{
"""
    for c in spec.classes :
        print "namespace %s" % (c.name)
        print "{"
        print "  enum { CLASS_ID = %d };" % (c.index)
        for m in c.methods:
            method_name = sanitizeName(m.name)
            print "  class AMQPP_EXPORT %s : public detail::method" % (method_name)
            print "  {"
            print "  public:"
            print "    typedef boost::shared_ptr<%s> ptr_t;" % (method_name)
            print "    enum { METHOD_ID = %d, CLASS_ID = %s::CLASS_ID };" % (m.index, c.name)
            print "    static ptr_t create() { return boost::make_shared<%s>(); }" % (method_name)
            print "    %s();" % (method_name)
            print "    virtual ~%s() {};" % (method_name)
            print ""
            print "    virtual uint16_t class_id() const { return %s::CLASS_ID; }" % (c.name)
            print "    virtual uint16_t method_id() const { return %s::METHOD_ID; }" % (method_name)
            print ""
            sync = 'false'
            if (m.isSynchronous) :
                sync = 'true'
            print "    virtual bool is_synchronous() const { return %s; }" % (sync)
            cont = 'false'
            if (m.hasContent) :
                cont = 'true'
            print "    virtual bool has_content() const { return %s; }" % (cont)
            print ""
            print "    static ptr_t read(std::istream& i);"
            print "    virtual void write(std::ostream& o) const;"
            print ""
            print "    virtual uint32_t get_serialized_size() const;"
            print "    virtual std::string to_string() const;"
            print ""
            for f in m.arguments:
                genGetter(f)
                genSetter(f)
            print ""
            print "  private:"
            for f in m.arguments:
                print "    %s m_%s;" % (types[spec.resolveDomain(f.domain)], sanitizeName(f.name))
            print "  };"
            print ""
        print "} //namespace %s" % (c.name)
        print ""

    print """} // namespace methods
#ifdef _MSC_VER
# pragma warning ( pop )
#endif
} // namespace amqpp
#endif // _LIBAMQPP_METHODS_GEN_H_INCLUDED_
"""

def genBody(spec):
    reader_writer = {
                     'octet':'uint8',
                     'short':'uint16',
                     'long':'uint32',
                     'longlong':'uint64',
                     'shortstr':'shortstring',
                     'longstr':'longstring',
                     'bit':'',
                     'table':'table',
                     'timestamp':'uint64'
                     }

    def getBitsLength(index, arguments):
        start = index
        while start > 0 and 'bit' == spec.resolveDomain(arguments[start - 1].domain):
            start -= 1
            
        end = index
        while end < len(arguments) and 'bit' == spec.resolveDomain(arguments[end].domain):
            end += 1
        
        return end - start
    
    def getBitsNumber(index, arguments):
        start = index
        while start > 0 and 'bit' == spec.resolveDomain(arguments[start - 1].domain):
            start -= 1
            
        return index - start
    
    def getBitfieldSize(length):
        if length <= 8:
            return 8
        elif length <=16:
            return 16
        elif length <= 32:
            return 32
        elif length <= 64:
            return 64
        else:
            raise Exception

    def genReadTopLevelFunction():
        print "method::ptr_t method::read(std::istream& i)"
        print "{"
        print "  uint16_t class_id = wireformat::read_uint16(i);"
        print "  uint16_t method_id = wireformat::read_uint16(i);"
        print "  switch (class_id)"
        print "  {"
        for c in spec.classes:
            print "  case methods::%s::CLASS_ID:" % (c.name)
            print "    switch (method_id)"
            print "    {"
            for m in c.methods:
                print "    case methods::%s::%s::METHOD_ID:" % (c.name, sanitizeName(m.name))
                print "      return methods::%s::%s::read(i);" % (c.name, sanitizeName(m.name))
            print "    default:"
            print '      throw std::runtime_error("Invalid method_id");'
            print "    }"
        print "  default:"
        print '    throw std::runtime_error("Invalid class_id");'
        print "  }"
        print "}"
        
    def genDefaultValue(field):
        domain = spec.resolveDomain(field.domain)
        if 'shortstr' == domain or 'longstr' == domain:
            return '"%s"' % (field.defaultvalue)
        elif 'bit' == domain:
            return 'true' if field.defaultvalue else 'false'
        else:
            return field.defaultvalue

    def genConstructor(method):
        method_name = sanitizeName(method.name)
        print "%s::%s()" % (method_name, method_name)
        arg_delimiter = ': '
        for field in method.arguments:
            domain = spec.resolveDomain(field.domain)
            if field.defaultvalue is not None and domain != 'table':
                print " %s m_%s(%s)" % (arg_delimiter, sanitizeName(field.name), genDefaultValue(field))
                arg_delimiter = ', '
        print "{"
        print "}"

    def genPrintFunction(method):
        method_name = sanitizeName(method.name)
        print "std::string %s::to_string() const" % (method_name)
        print "{"
        print "  std::ostringstream o;"
        print '  o << "class: %s<%d> method: %s<%d> {";' % (method.klass.name, method.klass.index, method.name, method.index)
        for field in method.arguments:
            domain = spec.resolveDomain(field.domain)
            if 'shortstr' == domain or 'longstr' == domain:
                print '  o << "%s<%s>: " << detail::print_string(get_%s()) << " ";' % (field.name, domain, sanitizeName(field.name))
            elif 'table' == domain:
                print '  o << "%s<%s>: " << get_%s().to_string() << " ";' % (field.name, domain, sanitizeName(field.name))
            elif 'octet' == domain:
                print '  o << "%s<%s>: " << static_cast<int>(get_%s()) << " ";' % (field.name, domain, sanitizeName(field.name))
            else:
                print '  o << "%s<%s>: " << get_%s() << " ";' % (field.name, domain, sanitizeName(field.name))
        print '  o << "}";'
        print "  return o.str();"
        print "}"

    def genReadBits(index, field, arguments):
        bit_number = getBitsNumber(index, arguments)
        bit_length = getBitsLength(index, arguments)
        bitsfield_length = getBitfieldSize(bit_length)
        if 0 == bit_number:
            print "  {"
            print "    uint%d_t bits = detail::wireformat::read_uint%d(i);" % (bitsfield_length, bitsfield_length)
        print "    ret->set_%s(detail::get_bit(bits, %d));" % (sanitizeName(field.name), bit_number)
        if bit_number == (bit_length - 1):
            print "  }"
        
    def genReadFunction(method):
        method_name = sanitizeName(method.name)
        print "%s::ptr_t %s::read(std::istream& i)" % (method_name, method_name)
        print "{"
        print "  %s::ptr_t ret = boost::make_shared<%s>();" % (method_name, method_name)
        for index, field in enumerate(method.arguments):
            domain = spec.resolveDomain(field.domain)
            if domain == 'bit':
                genReadBits(index, field, method.arguments)
            elif domain == 'table':
                print "  ret->get_%s() = detail::wireformat::read_table(i);" % (sanitizeName(field.name))
            else:
                print "  ret->set_%s(detail::wireformat::read_%s(i));" % (sanitizeName(field.name), reader_writer[domain])
        print "  return ret;"
        print "}"

        
        
    def genWriteBits(index, field, arguments):
        bit_number = getBitsNumber(index, arguments)
        bit_length = getBitsLength(index, arguments)
        bitfield_length = getBitfieldSize(bit_length)
        if 0 == bit_number:
            print "  {"
            print "    uint%d_t bits = 0;" % (bitfield_length)
        print "    bits = detail::set_bit(bits, m_%s, %d);" % (sanitizeName(field.name), bit_number)
        if bit_number == (bit_length - 1):
            print "    detail::wireformat::write_uint%d(o, bits);" % (bitfield_length)
            print "  }"
            
    
    def genWriteFunction(method):
        method_name = sanitizeName(method.name)
        print "void %s::write(std::ostream& o) const" % (method_name)
        print "{"
        print "  detail::wireformat::write_uint16(o, static_cast<uint16_t>(%s::CLASS_ID));" % (method.klass.name)
        print "  detail::wireformat::write_uint16(o, static_cast<uint16_t>(%s::METHOD_ID));" % (method_name)
        for index, field in enumerate(method.arguments):
            domain = spec.resolveDomain(field.domain)
            if domain == 'bit':
                genWriteBits(index, field, method.arguments)
            else:
                print "  detail::wireformat::write_%s(o, m_%s);" % (reader_writer[domain], sanitizeName(field.name))
        print "}"

    def genGetLengthFunction(method):
        size_map = {
                     'octet':'sizeof(uint8_t)',
                     'short':'sizeof(uint16_t)',
                     'long':'sizeof(uint32_t)',
                     'longlong':'sizeof(uint64_t)',
                     'timestamp' : 'sizeof(uint64_t)'
                     }

        method_name = sanitizeName(method.name)
        print "uint32_t %s::get_serialized_size() const" % (method_name)
        print "{"
        print "  uint32_t size = sizeof(uint16_t) + sizeof(uint16_t); // class and method"
        for index, field in enumerate(method.arguments):
            domain = spec.resolveDomain(field.domain)
            if domain == 'bit':
                bits_len = getBitsLength(index, method.arguments)
                bits_index = getBitsNumber(index, method.arguments)
                if bits_index == (bits_len - 1):
                    print "  size += sizeof(uint%d_t); // %s" % (getBitfieldSize(bits_len), field.name)
                else:
                    print "  // %s" % (field.name)
            elif domain == 'shortstr':
                print "  size += sizeof(uint8_t) + static_cast<uint32_t>(m_%s.length());" % (sanitizeName(field.name))
            elif domain == 'longstr':
                print "  size += sizeof(uint32_t) + static_cast<uint32_t>(m_%s.length());" % (sanitizeName(field.name))
            elif domain == 'table':
                print "  size += m_%s.wireformat_size();" % (sanitizeName(field.name))
            else:
                print "  size += %s; // %s" % (size_map[domain], field.name)
        print "  return size;"
        print "}"

    print """// Autogenerated code. Do not edit. Edit codegen.py instead
#include "methods.gen.h"
#include "detail/bitset.h"
#include "detail/string_utils.h"
#include "detail/wireformat.h"

#include <boost/make_shared.hpp>

#include <istream>
#include <ostream>
#include <sstream>

namespace amqpp
{
namespace detail
{
"""
    genReadTopLevelFunction()
    print """} // namespace detail"
namespace methods
{"""
    for c in spec.classes :
        print "namespace %s" % (c.name)
        print "{"
        for m in c.methods:
            genConstructor(m)
            print ""
            genPrintFunction(m)
            print ""
            genReadFunction(m)
            print ""
            genGetLengthFunction(m)
            print ""
            genWriteFunction(m)
            print ""
        print "} // namespace %s" % (c.name)

    print """
} // namespace methods
} //namespace amqpp
"""


def generateHeader(specPath):
    genHeader(AmqpSpec(specPath))

def generateSource(specPath):
    genBody(AmqpSpec(specPath))

if __name__ == "__main__":
    do_main(generateHeader, generateSource)
