// Set $nodes_uri and $edges_uri to CSV files in your Neo4j import directory.
CREATE CONSTRAINT code_entity_id IF NOT EXISTS FOR (n:CodeEntity) REQUIRE n.id IS UNIQUE;
LOAD CSV WITH HEADERS FROM $nodes_uri AS row
MERGE (n:CodeEntity {id: row.id})
SET n.repo=row.repo, n.revision=row.revision, n.kind=row.kind,
    n.path=row.path, n.qualified_name=row.qualified_name,
    n.start=toInteger(row.start), n.end=toInteger(row.end);
LOAD CSV WITH HEADERS FROM $edges_uri AS row
MATCH (a:CodeEntity {id:row.source}), (b:CodeEntity {id:row.target})
FOREACH (_ IN CASE row.relation WHEN 'CALLS' THEN [1] ELSE [] END | MERGE (a)-[r:CALLS]->(b) SET r.line=toInteger(row.line), r.resolution=row.resolution)
FOREACH (_ IN CASE row.relation WHEN 'CONTAINS' THEN [1] ELSE [] END | MERGE (a)-[r:CONTAINS]->(b) SET r.line=toInteger(row.line), r.resolution=row.resolution)
FOREACH (_ IN CASE row.relation WHEN 'IMPORTS' THEN [1] ELSE [] END | MERGE (a)-[r:IMPORTS]->(b) SET r.line=toInteger(row.line), r.resolution=row.resolution)
FOREACH (_ IN CASE row.relation WHEN 'INHERITS' THEN [1] ELSE [] END | MERGE (a)-[r:INHERITS]->(b) SET r.line=toInteger(row.line), r.resolution=row.resolution);
