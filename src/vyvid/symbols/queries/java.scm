; Adapted from tree-sitter-java, which is MIT licensed and copyright its authors.
; From tree-sitter-java's queries/tags.scm (its @definition.* patterns). Its references are dropped. The enum, record, annotation, constructor and field patterns are ours, since the shipped file has none.
(class_declaration name: (identifier) @name) @definition.class
(interface_declaration name: (identifier) @name) @definition.interface
(enum_declaration name: (identifier) @name) @definition.enum
(record_declaration name: (identifier) @name) @definition.record
(annotation_type_declaration name: (identifier) @name) @definition.annotation
(method_declaration name: (identifier) @name) @definition.method
(constructor_declaration name: (identifier) @name) @definition.constructor
(field_declaration declarator: (variable_declarator name: (identifier) @name)) @definition.field
