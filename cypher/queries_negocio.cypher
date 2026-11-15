// ============================================================================
// Queries de negócio — Grafo da legislação brasileira
// Cada bloco é uma pergunta que o modelo responde.
// Rode no Neo4j Browser, no Bloom ou via scripts/run_query.py
// ============================================================================

// ----------------------------------------------------------------------------
// Q1. Quantas normas vigentes existem, por tipo?
// Pergunta de negócio: "Qual é a composição do acervo normativo federal?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
RETURN n.tipo AS tipo, count(*) AS normas
ORDER BY normas DESC;

// ----------------------------------------------------------------------------
// Q2. Quais são as leis que mais revogam outras leis?
// Pergunta: "Quais normas foram os grandes 'faxineiros' do ordenamento?"
// A relação REVOGA vai da norma revogadora para a revogada.
// ----------------------------------------------------------------------------
MATCH (revogadora:Norma)-[r:REVOGA]->()
RETURN revogadora.titulo AS norma,
       revogadora.tipo AS tipo,
       revogadora.ano AS ano,
       count(r) AS revogacoes
ORDER BY revogacoes DESC
LIMIT 10;

// ----------------------------------------------------------------------------
// Q3. Quais normas são o centro do ordenamento (mais citadas)?
// Pergunta: "Se eu estudar poucas leis, quais devo priorizar?"
// Grau de entrada alto = norma estruturante, citada por muitas outras.
// ----------------------------------------------------------------------------
MATCH (n:Norma)<-[r]-()
RETURN n.titulo AS norma, n.tipo AS tipo, n.ano AS ano,
       count(r) AS citacoes,
       count(DISTINCT type(r)) AS tipos_de_relacao
ORDER BY citacoes DESC
LIMIT 10;

// ----------------------------------------------------------------------------
// Q4. Cadeias de revogação: quem revogou quem revogou quem
// Pergunta: "Existe norma que revogou outra que já havia revogado?"
// Mostra até 3 saltos — bom exemplo de por que grafo e não tabela.
// ----------------------------------------------------------------------------
MATCH caminho = (a:Norma)-[:REVOGA*2..3]->(c:Norma)
RETURN a.titulo AS origem, c.titulo AS destino,
       length(caminho) AS saltos
LIMIT 15;

// ----------------------------------------------------------------------------
// Q5. Normas que alteram e são alteradas (nós de convergência)
// Pergunta: "Quais normas são ao mesmo tempo alvo e fonte de mudanças?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WITH n,
     size([(n)-[:ALTERA]->() | 1]) AS altera,
     size([(n)<-[:ALTERA]-() | 1]) AS alterada_por
WHERE altera > 0 AND alterada_por > 0
RETURN n.titulo AS norma, altera, alterada_por,
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
// Q7. Decomposição do Código Civil (Lei 10.406/2002): o que o alterou?
// Pergunta: "Quais normas modificaram o Código Civil desde 2002?"
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
// Útil para medir a densidade real do grafo.
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WHERE NOT (n)-[]-()
RETURN count(*) AS normas_isoladas;

// ----------------------------------------------------------------------------
// Q9. Componentes conexos: o ordenamento é um bloco só ou ilhas?
// Pergunta: "A legislação federal forma uma malha conectada?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)
WHERE (n)-[]-()
WITH n LIMIT 5000
RETURN count(DISTINCT n) AS amostra_conectada;
// Alternativa com GDS (se instalado):
// CALL gds.graph.project('legis', 'Norma', '*');
// CALL gds.wcc.stream('legis') YIELD componentId
// RETURN count(DISTINCT componentId) AS componentes;

// ----------------------------------------------------------------------------
// Q10. Norma mais conectada por esfera (demonstra multiesfera)
// Pergunta: "Qual é a norma-âncora de cada esfera?"
// ----------------------------------------------------------------------------
MATCH (n:Norma)-[r]-()
WITH n.esfera AS esfera, n, count(r) AS grau
ORDER BY grau DESC
WITH esfera, collect(n.titulo)[0] AS norma_ancora, collect(grau)[0] AS grau_max
RETURN esfera, norma_ancora, grau_max;
