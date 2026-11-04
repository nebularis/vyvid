; Adapted from tree-sitter-python, which is MIT licensed and copyright its authors.
; From tree-sitter-python's queries/tags.scm (its @definition.* patterns, unchanged). Its @reference.call pattern is dropped, since a call is no symbol.
(module (expression_statement (assignment left: (identifier) @name) @definition.constant))

(class_definition
  name: (identifier) @name) @definition.class

(function_definition
  name: (identifier) @name) @definition.function
