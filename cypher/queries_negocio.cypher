// ============================================================================
// Queries de negócio — Grafo da legislação brasileira
// Cada bloco é uma pergunta que o modelo responde.
// Rode no Neo4j Browser, no Bloom ou via scripts/run_query.py
//
// DIREÇÃO DAS ARESTAS (leia antes de escrever novas queries):
//   REVOGA / ALTERA / INCLUI  ->  (citada)-[efeito]->(contém a anotação)
//       A norma nomeada na anotação é quem produziu o efeito.
//       "*(Revogado pela Lei nº 9.120/1995)*" dentro da Lei 3.820/1960
//       gera (9120)-[:REVOGA]->(3820).
//   REFERENCIA                ->  (contém o "Vide")-[cita]->(citada)
//       Quem traz a remissão é a origem.
// ============================================================================

// ----------------------------------------------------------------------------
// Q1. Como se compõe o acervo carregado, por tipo de norma?
// Pergunta: "Qual é o perfil do acervo federal?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
RETURN n.tipo AS tipo, count(*) AS normas
ORDER BY normas DESC;

// ----------------------------------------------------------------------------
// Q2. Quais normas revogaram mais outras?
// Pergunta: "Quais leis foram os grandes 'faxineiros' do ordenamento?"
// A aresta sai de quem revogou — por isso o padrão é (revogadora)-[:REVOGA]->().
// ----------------------------------------------------------------------------
MATCH (revogadora:Norma)-[r:REVOGA]->()
RETURN revogadora.titulo AS norma,
       revogadora.ano AS ano,
       count(r) AS revogacoes
ORDER BY revogacoes DESC
LIMIT 10;

// ----------------------------------------------------------------------------
// Q3. Quais normas são o centro do ordenamento (mais afetadas e citadas)?
// Pergunta: "Se eu estudar poucas normas, quais priorizar?"
// Grau de entrada = quantas normas produziram algum efeito sobre esta.
// ----------------------------------------------------------------------------
MATCH (n:Norma)<-[r]-()
RETURN n.titulo AS norma, n.ano AS ano,
       count(r) AS citacoes,
       count(DISTINCT type(r)) AS tipos_de_relacao
ORDER BY citacoes DESC
LIMIT 10;

// ----------------------------------------------------------------------------
// Q4. Existem cadeias de revogação (A revogou B, que já havia revogado C)?
// Pergunta: "Há revogação em cascata no ordenamento?"
// É a pergunta que justifica grafo: em SQL exigiria CTE recursiva.
// ----------------------------------------------------------------------------
MATCH caminho = (a:Norma)-[:REVOGA*2..3]->(c:Norma)
RETURN a.titulo AS origem, c.titulo AS destino, length(caminho) AS saltos
LIMIT 15;

// ----------------------------------------------------------------------------
// Q5. Normas que alteram e são alteradas (nós de convergência)
// Pergunta: "Quais normas são ao mesmo tempo fonte e alvo de mudanças?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WITH n,
     size([(n)-[:ALTERA]->() | 1]) AS altera,
     size([(n)<-[:ALTERA]-() | 1]) AS alterada_por
WHERE altera > 0 AND alterada_por > 0
RETURN n.titulo AS norma, n.ano AS ano, altera, alterada_por,
       altera + alterada_por AS centralidade
ORDER BY centralidade DESC
LIMIT 10;

// ----------------------------------------------------------------------------
// Q6. Evolução do volume legislativo por década
// Pergunta: "Em que período o Brasil mais legislou?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WHERE n.ano IS NOT NULL AND n.ano >= 1820
RETURN (n.ano / 10) * 10 AS decada, count(*) AS normas
ORDER BY decada;

// ----------------------------------------------------------------------------
// Q7. O que alterou o Código Civil (Lei 10.406/2002)?
// Pergunta: "Quais normas modificaram o Código Civil desde 2002?"
// Note o "<-": as alteradoras apontam PARA o Código Civil.
// ----------------------------------------------------------------------------
MATCH (cc:Norma {numero: '10406', ano: 2002})
MATCH (alteradora:Norma)-[r:ALTERA|REVOGA]->(cc)
RETURN type(r) AS relacao, alteradora.titulo AS norma,
       alteradora.ano AS ano, r.trecho AS trecho
ORDER BY ano DESC
LIMIT 20;

// ----------------------------------------------------------------------------
// Q8. Normas órfãs: não citam nem são citadas
// Pergunta: "Que parte do acervo está isolada do resto?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WHERE NOT (n)-[]-()
RETURN count(*) AS normas_isoladas;

// ----------------------------------------------------------------------------
// Q9. O que cita uma norma específica (quem remete a ela)?
// Pergunta: "Quais normas invocam o Estatuto da Criança e do Adolescente?"
// Aqui a aresta REFERENCIA sai de quem traz o "Vide".
// ----------------------------------------------------------------------------
MATCH (origem:Norma)-[r:REFERENCIA]->(eca:Norma {numero: '8069', ano: 1990})
RETURN origem.titulo AS quem_cita, origem.ano AS ano, r.trecho AS trecho
ORDER BY ano DESC
LIMIT 15;

// ----------------------------------------------------------------------------
// Q10. Grau de cada norma: quantas a afetaram e quantas ela afetou
// Pergunta: "Qual o balanço de influência desta norma no ordenamento?"
// Use para mostrar que a direção importa: as duas colunas não se confundem.
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WHERE n.numero IN ['8212', '8213', '10406', '8069', '9503']
WITH n,
     size([(n)<-[]-() | 1]) AS recebeu,
     size([(n)-[]->() | 1]) AS produziu
RETURN n.titulo AS norma, n.ano AS ano, recebeu, produziu,
       recebeu - produziu AS saldo
ORDER BY recebeu DESC;
