import csv
from keboola import docker

def is_null_value(value):
  return value == '' or value == '0'

def get_rest(row, child_column):
  return {k: row[k] for k in row if k != child_column }


def parse_tree(rows, parent_column, child_column):
  grouped_relations = {}
  roots = set()
  rest = {}
  for row in rows:
    parent = row[parent_column]
    child = row[child_column]
    rest[child] = get_rest(row, child_column)
    if is_null_value(parent):
      roots.add(child)
    else:
      group = grouped_relations.get(parent, set())
      group.add(child)
      grouped_relations[parent] = group
  return roots, grouped_relations, rest

def walk_tree_r(node, relations, level, root):
  yield (node, level, root)
  for child in relations.get(node, set()):
    yield from walk_tree_r(child, relations, level + 1, root)

def walk_tree(roots, relations):
  for root in roots:
    yield from walk_tree_r(root, relations, 1, root)

def run(datadir):
  cfg = docker.Config(datadir)
  parameters = cfg.get_parameters()
  c_parent = parameters.get('parentColumn', 'categoryParentId')
  c_child = parameters.get('idColumn', 'categoryId')

  # get input and output table and validate them
  tables = cfg.get_input_tables()
  if len(tables) != 1:
      raise ValueError("Input mapping must contain one table only.")
  in_table = tables[0]
  tables = cfg.get_expected_output_tables()
  if len(tables) != 1:
      raise ValueError("Output mapping must contain one table only.")
  out_table = tables[0]
  # physical location of the source file with source data
  in_file_path = in_table['full_path']
  # physical location of the target file with output data
  out_file_path = out_table['full_path']
  roots = set()
  relations = {}
  input_csv_header = []
  with open(in_file_path, mode='rt', encoding='utf-8') as in_file:
    lazy_lines = (line.replace('\0', '') for line in in_file)
    csv_reader = csv.DictReader(lazy_lines, dialect='kbc')
    input_csv_header = csv_reader.fieldnames
    roots, relations, rest = parse_tree(csv_reader, c_parent, c_child)

  with open(out_file_path, mode='wt', encoding='utf-8') as out_file:
    out_csv_header = input_csv_header + ['levels', 'root']
    writer = csv.DictWriter(out_file, fieldnames = out_csv_header, dialect='kbc')
    writer.writeheader()
    for  child, level, root in walk_tree(roots, relations):
      base_row = {c_child: child, 'levels': level, 'root': root}
      rest_row = rest[child]
      out_row = {**base_row, **rest_row}
      writer.writerow(out_row)
