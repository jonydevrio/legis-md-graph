// ============================================================================
// Modelo do grafo — Grafo da Legislação Brasileira (Neo4j)
// Cole no Arrows.app (https://arrows.app) para editar visualmente.
// Também serve como documentação do schema.
// ============================================================================
//
//  (:Norma)
//     id            "federal:BR:L:10406/2002"   <- chave única (constraint)
//     titulo        "Lei nº 10.406 de 10/01/2002"
//     tipo          "Lei Ordinária" | "Lei Complementar" | "Emenda Constitucional" | ...
//     numero        "10406"
//     ano           2002            <- inteiro, usado em filtros e ordenação
//     data          "2002-01-10"
//     esfera        "federal" | "estadual" | "municipal" | "regulador" | ...
//     uf            "SP" | null      <- null na esfera federal
//     ementa        "Institui o Código Civil."
//     situacao      "Não consta revogação expressa" | ...
//     vigente       true | false
//     vigencia_origem  como se chegou à conclusão (auditoria)
//     versao_texto  "original" | "compilada (texto vigente)" | ...
//     urn / fonte / arquivo
//
//  Relações (todas com propriedade `trecho`, o texto que a originou):
//
//    (:Norma)-[:REVOGA]->(:Norma)       a origem revogou a destino
//    (:Norma)-[:ALTERA]->(:Norma)       redação dada / alterado por
//    (:Norma)-[:INCLUI]->(:Norma)       dispositivo incluído
//    (:Norma)-[:REFERENCIA]->(:Norma)   "Vide" — remissão sem alterar
//
//  Direção: sempre da norma que produz o efeito para a que o recebe.
//  Assim, `MATCH (a)-[:REVOGA]->(b)` lê-se "a revogou b", e o grau de
//  entrada de um nó mede quantas normas o afetaram.
// ============================================================================

CREATE (n:Norma {
  id: 'federal:BR:L:10406/2002',
  titulo: 'Lei nº 10.406 de 10/01/2002',
  tipo: 'Lei Ordinária',
  numero: '10406',
  ano: 2002,
  data: '2002-01-10',
  esfera: 'federal',
  uf: null,
  ementa: 'Institui o Código Civil.',
  situacao: 'Não consta revogação expressa',
  vigente: true,
  versao_texto: 'compilada (texto vigente)',
  urn: 'urn:lex:br:federal:lei:2002-01-10;10406'
});

CREATE (ec:Norma {
  id: 'federal:BR:EC:32/2001',
  titulo: 'Emenda Constitucional nº 32 de 11/09/2001',
  tipo: 'Emenda Constitucional',
  numero: '32',
  ano: 2001,
  esfera: 'federal',
  vigente: true
});

CREATE (lc:Norma {
  id: 'federal:BR:LC:214/2025',
  titulo: 'Lei Complementar nº 214 de 16/01/2025',
  tipo: 'Lei Complementar',
  numero: '214',
  ano: 2025,
  esfera: 'federal',
  vigente: true
});

CREATE (l13874:Norma {
  id: 'federal:BR:L:13874/2019',
  titulo: 'Lei nº 13.874 de 20/09/2019',
  tipo: 'Lei Ordinária',
  numero: '13874',
  ano: 2019,
  esfera: 'federal',
  vigente: true
});

// Exemplo de relações: o Código Civil foi alterado pela Lei 13.874 e é
// referência na LC 214; a EC 32 é citada por muitas normas.
MATCH (cc:Norma {id: 'federal:BR:L:10406/2002'})
MATCH (l:Norma {id: 'federal:BR:L:13874/2019'})
MERGE (l)-[:ALTERA {trecho: 'Redação dada pela Lei nº 13.874, de 2019'}]->(cc);

MATCH (cc:Norma {id: 'federal:BR:L:10406/2002'})
MATCH (lc:Norma {id: 'federal:BR:LC:214/2025'})
MERGE (lc)-[:REFERENCIA {trecho: 'Vide Lei nº 10.406, de 2002'}]->(cc);
