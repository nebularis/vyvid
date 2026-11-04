; Ours entirely: tree-sitter-haskell ships highlights, injections and locals but no tags.scm.
; A signature names one or more functions. Only a top-level or class-body signature is a symbol, so a where-bound one is not.
(declarations (signature . [(variable) @name (prefix_id (operator) @name) (binding_list [(variable) @name (prefix_id (operator) @name)])]) @definition.function)
(class_declarations (signature . [(variable) @name (prefix_id (operator) @name) (binding_list [(variable) @name (prefix_id (operator) @name)])]) @definition.method)
; A top-level definition with no signature.
(declarations (function . (variable) @name) @definition.unsigned)
(declarations (function . (infix (operator) @name)) @definition.unsigned)
(declarations (bind . (variable) @name) @definition.unsigned)
; Types.
(declarations (data_type (name) @name) @definition.data)
(declarations (newtype (name) @name) @definition.newtype)
(declarations (type_synonym (name) @name) @definition.type)
(declarations (data_family (name) @name) @definition.data-family)
(declarations (type_family (name) @name) @definition.type-family)
(declarations (class (name) @name) @definition.class)
(declarations (instance (name) @name) @definition.instance)
; Constructors and fields.
(data_constructor (prefix . (constructor) @name)) @definition.constructor
(data_constructor (record . (constructor) @name)) @definition.constructor
(data_constructor (infix (constructor_operator) @name)) @definition.constructor
(newtype_constructor (constructor) @name) @definition.constructor
(gadt_constructor (constructor) @name) @definition.constructor
(field (field_name (variable) @name)) @definition.field
