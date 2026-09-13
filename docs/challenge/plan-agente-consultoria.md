# Plan de desarrollo y entrenamiento — Agente de consultoría forense

**Fuente:** `docs/challenge/reporte-gaps.md` (corte 2026-09-12)  
**Objetivo:** llevar al agente de un flujo demostrativo con fallback a un
consultor forense auditable: investiga leads reales, fundamenta sus
conclusiones en evidencia recuperable y responde preguntas sin inventar
hechos.

## Principios de ejecución

- El LLM decide el siguiente paso dentro del protocolo; Python conserva la
  autoridad sobre cálculos, trazas, detección, exposición y estados del caso.
- Toda afirmación del agente debe incluir `source_ids`, `provenance` y
  referencias a evidencia o pasos de investigación.
- EFOS/69-B es contexto, no prueba autónoma de fraude.
- Las herramientas son tipadas, sólo lectura, con límites de tiempo y de
  profundidad. El agente nunca recibe SQL, shell ni acceso de escritura.
- "Entrenar" en este plan significa diseñar instrucciones, ejemplos y
  evaluaciones reproducibles para el proveedor elegido. No se debe plantear
  fine-tuning hasta contar con datos revisados, desidentificados y un conjunto
  de evaluación estable.

## Orden de fases y gaps

Las fases preservan la prioridad y el orden del reporte. Un gap sólo se
considera cerrado cuando cumple sus criterios de salida y las pruebas
indicadas; una UI que aparenta el comportamiento no es evidencia de cierre.

### Fase 0 — Línea base y definición de contratos

**Propósito:** establecer los artefactos que permitirán medir cada cambio del
agente sin alterar todavía su criterio de negocio.

**Gaps cubiertos**

1. **P2.5 — Reparar documentación desactualizada.** Corregir rutas,
   dependencias y afirmaciones de capacidades ya obsoletas en `docs/testing.md`
   y en los contratos. Registrar las decisiones de compatibilidad o ruptura.
2. **P3.4 — Reconciliar README, arquitectura, runbook y contratos.** Mantener
   esta tarea abierta hasta el final: actualizar los documentos al cerrar cada
   fase y consolidarlos al final.

**Entregables**

- Matriz de trazabilidad `gap → contrato → módulo → prueba → escenario`.
- Inventario de contratos vigentes y decisión explícita sobre compatibilidad
  temporal de endpoints/herramientas.
- Línea base reproducible: `pytest -q`, `python scripts/verify_demo.py`,
  `python scripts/run_demo.py` y `npm run build` guardados como evidencia.

**Criterio de salida:** cada requisito del runbook apunta a un endpoint,
herramienta o prueba existente; las discrepancias conocidas están anotadas,
no implícitas.

---

### Fase 1 — Investigación y caso derivados de evidencia real

**Propósito:** eliminar los casos y conclusiones codificados de forma fija
antes de hacer que el agente investigue más rápido o con más herramientas.

**Gap cubierto**

1. **P1.1 — Derivar la investigación y el caso de registros reales.**
   - Resolver las contrapartes a partir de las transacciones, pagos, facturas
     y entidades del lead.
   - Sustituir proveedor y monto fijos por el cálculo de exposición de las
     transacciones raíz, sin sumar hops intermedios.
   - Integrar `EvidenceCollector.evaluate_finding()` para crear afirmaciones
     verificables, con fuente y procedencia.
   - Determinar el estado del caso con reglas explícitas:
     `SUBSTANTIATED`, `UNSUBSTANTIATED` o `INSUFFICIENT_EVIDENCE`.

**Entregables**

- Constructor de caso basado en el rastro y sus `source_ids`.
- Pruebas de los tres estados, de contrapartes correctas y de ausencia de
  doble conteo de exposición.
- Fixtures positivos, negativos y con evidencia incompleta.

**Criterio de salida:** al cambiar el lead o escenario, cambian coherentemente
el proveedor, el monto, el rastro, la evidencia y la conclusión. Ninguno de
esos campos se obtiene de constantes de demo.

---

### Fase 2 — Orquestación segura y superficie de herramientas

**Propósito:** hacer que el agente consulte datos válidos, avance en cada
turno y pueda explicar de dónde obtuvo cada resultado.

**Gaps cubiertos**

1. **P1.2 — Corregir el loop del agente y el fallback.**
   - Validar argumentos contra el esquema de cada herramienta antes de
     ejecutarla; corregir la traza para enviar la cuenta de origen y el límite
     de hops que espera el contrato.
   - Persistir resultados y referencias entre turnos.
   - Requerir evidencia nueva o una hipótesis más específica en cada
     decisión `FOLLOW`; detectar hashes, llamadas y resultados repetidos.
   - Finalizar por conclusión, descarte, escalamiento o presupuesto agotado.
     Al agotarse el presupuesto, registrar `ESCALATE`, motivo y evidencia
     disponible.
2. **P1.3 — Alinear la superficie de herramientas con su contrato.**
   - Decidir si se implementan las catorce herramientas de
     `docs/contracts/agent-tools.md` o se reduce formalmente el contrato.
   - Unificar los nombres y entradas incompatibles entre contratos, por
     ejemplo trazas por `account_no` frente a pasos que refieren
     `transaction_id`.
   - Normalizar todas las respuestas como
     `{result, provenance, source_ids, execution_time, errors}`.
   - Cubrir cada herramienta con pruebas unitarias y de contrato.

**Entregables**

- Máquina de estados delimitada por pasos, tiempo, profundidad y presupuesto.
- Adaptador de validación de argumentos/respuestas de herramientas.
- Registro de `InvestigationStep` que contiene decisión, entradas, referencias
  de resultado, razón y hash completo de cada ejecución.
- Fallback determinista que usa la misma máquina de estados y las mismas
  herramientas tipadas que la ruta de proveedor.

**Criterio de salida:** un escenario de ciclo ejecuta una traza válida, no
repite llamadas equivalentes y termina con `CONCLUDE`, `DISCARD` o `ESCALATE`
observables. Todas las salidas de herramienta cumplen el contrato.

---

### Fase 3 — Datos persistentes y escenarios reproducibles

**Propósito:** evitar que el agente investigue sólo un estado en memoria y
garantizar que el demo, la base de datos y los datasets representen el mismo
hecho.

**Gaps cubiertos**

1. **P1.4 — Implementar persistencia de producto.**
   - Crear repositorios PostgreSQL que cumplan los protocolos actuales y
     conectar `DATABASE_URL` a servicios y API.
   - Persistir datasets, leads, pasos, evidencia y casos.
   - Ejecutar migraciones y carga de seed desde Compose o mediante un seeder
     explícito.
   - Unificar `demo_scenario.py` y `database/seeds/001_demo.sql` en un
     escenario canónico, incluido el ciclo $1M → $920k → $740k.
2. **P2.3 — Conectar parsers a importación de escenarios.**
   - Convertir CFDI XML, CSV bancario y EFOS 69-B en `CanonicalDataset`.
   - Rechazar y reportar registros inválidos sin ocultar errores de
     normalización.
   - Añadir datasets y answer keys por patrón; la fuente EFOS conserva su
     condición contextual.

**Entregables**

- Implementación de repositorios con pruebas contra PostgreSQL.
- Seeder idempotente del escenario canónico y comando documentado de carga.
- Pipeline de importación con reporte de aceptados, rechazados y
  deduplicados.

**Criterio de salida:** iniciar el entorno desde cero produce el mismo
dataset que el demo; el agente puede reiniciar una investigación persistida y
recuperar exactamente sus pasos y evidencia.

---

### Fase 4 — Experiencia demostrable y consultoría auditable

**Propósito:** exponer la investigación real al juez y al usuario sin
desacoplar frontend, API y evidencia.

**Gaps cubiertos**

1. **P1.5 — Cerrar el contrato de demo/API.**
   - Implementar los endpoints comprometidos o actualizar el contrato con
     una decisión aprobada; no mantener contratos ficticios.
   - Añadir `POST /demo/inject-fraud` para introducir un escenario oculto,
     descarte visible de lead y stream/consulta de eventos de pasos.
2. **P1.6 — Hacer la visualización y Q&A auditables.**
   - Construir `MoneyTrailGraph` con nodos y aristas del caso seleccionado,
     no de un fixture fijo.
   - Responder preguntas a partir de evidencia y pasos recuperados, siempre
     con `evidence_refs`; si no hay soporte, responder insuficiencia.

**Entregables**

- API de casos, investigación, grafo, evidencia, eventos, preguntas e
  inyección alineada al contrato definitivo.
- Timeline de pasos estructurados, vista de descarte y grafo dinámico.
- Pruebas de contrato API y pruebas de componentes para estados con/sin
  evidencia.

**Criterio de salida:** el runbook permite inyectar fraude, verlo como lead,
seguir la investigación en tiempo real, abrir las fuentes y obtener una
respuesta que cita la evidencia del caso correcto.

---

### Fase 5 — Cobertura analítica y preparación de datos de entrenamiento

**Propósito:** ampliar la calidad de los leads sin delegar detección al LLM y
crear los ejemplos con los que se evaluará el comportamiento del agente.

**Gaps cubiertos**

1. **P2.1 — Completar la biblioteca de detectores documentada.** Implementar
   factura duplicada, monto inusual, concentración, conciliación
   factura-pago, fan-in, fan-out, red de empresas pantalla, correlación 69-B
   y timing inusual. Todos emiten `DetectorSignal` determinista con fuentes;
   la agregación aplica pesos y umbrales documentados.
2. **P2.2 — Corregir pass-through y deduplicar ciclos.** Extender modelo y
   fuentes con timestamp; evaluar orden temporal, ventana y relación de
   importes reales. Normalizar ciclos equivalentes para producir un solo lead.

**Entregables**

- Registro de detectores, señales explicables y agregador determinista.
- Escenarios positivos y negativos por detector, con answer keys.
- Corpus de evaluación del agente por escenario: lead de entrada, herramientas
  permitidas, rastro esperado, evidencia mínima, decisión terminal esperada y
  preguntas de auditoría.

**Criterio de salida:** dos ejecuciones con el mismo dataset producen las
mismas señales, leads y answer keys. Los escenarios negativos no generan una
acusación por EFOS ni por similitud superficial.

---

### Fase 6 — Entrenamiento operativo y validación end-to-end

**Propósito:** ajustar el agente contra casos medibles y prevenir regresiones
del flujo completo.

**Gaps cubiertos**

1. **P2.4 — Añadir pruebas de integración, contrato, componentes y E2E.**
   - Ejecutar integración real contra PostgreSQL.
   - Convertir `tests/e2e/` de documentación a recorridos ejecutables:
     `dataset → detector → lead → agente → caso → API → frontend`.
   - Probar contrato de herramientas/API, fallback sin red y escenarios
     inyectados.

**Plan de entrenamiento del agente**

1. **Definir la política.** Convertir el protocolo en instrucciones
   versionadas: cómo seleccionar una herramienta, cuándo seguir, descartar,
   escalar o concluir, y qué evidencia mínima requiere cada conclusión.
2. **Construir conjuntos separados.** Dividir escenarios por esquema de
   fraude y entidad para evitar que variaciones del mismo ciclo aparezcan en
   entrenamiento y evaluación. Incluir casos legítimos y evidencia
   insuficiente.
3. **Ajustar con ejemplos.** Usar few-shot o configuración del proveedor con
   pasos estructurados de alta calidad. Mantener prompt, modelo, parámetros,
   versión de herramientas y seed de evaluación en el resultado.
4. **Evaluar por ejecución.** Medir validez de argumentos, llamadas repetidas,
   cobertura de fuentes, precisión del estado terminal, exactitud de
   exposición, referencias de Q&A, longitud de investigación y tasa de
   escalamiento apropiado.
5. **Promover con umbrales.** Un cambio de prompt/modelo sólo pasa si no
   reduce las métricas de casos legítimos, no pierde procedencia y supera los
   umbrales acordados en el conjunto bloqueado.
6. **Considerar fine-tuning sólo después.** Requerirá revisión legal y de
   privacidad, desidentificación, trazabilidad de etiquetas, conjunto de
   evaluación retenido y una ganancia demostrada frente a prompt + tools.

**Criterio de salida:** la suite E2E es reproducible y bloquea una versión
del agente que inventa fuentes, repite una herramienta, calcula exposición
incorrecta o acusa sin evidencia suficiente.

---

### Fase 7 — Operación, resiliencia y despliegue

**Propósito:** convertir el flujo validado en un servicio observable y
recuperable.

**Gaps cubiertos**

1. **P3.1 — Usar presupuesto, proveedores y telemetría.** Hacer efectivos
   `config/agent-providers.yaml`, presupuesto de sesión, métricas de uso y
   failover, preservando la razón de cambio de proveedor.
2. **P3.2 — Completar despliegue documentado.** Incorporar frontend a Compose,
   health/readiness checks, configuración de producción y runbook de
   recuperación probado.
3. **P3.3 — Mejorar trazabilidad operativa.** Persistir eventos, hashes
   completos, historial y métricas de detector/modelo; añadir concurrencia,
   paginación y errores visibles en UI.

**Criterio de salida:** un reinicio, fallo de proveedor o investigación
concurrente no elimina trazabilidad ni permite que el agente supere sus
límites. El runbook de recuperación ha sido ejecutado y verificado.

## Hitos de demostración

1. **Hito A (Fases 1–2) — implementado en código (2026-09-12):** un lead
   real del ciclo canónico genera evidencia con `source_ids` de transacciones,
   exposición raíz de $1,000,000 MXN, proveedores por RFC y un loop offline
   válido (sin llamadas repetidas ni args inválidos). Control compartido no se
   sustenta. Criterio medido por `tests/unit/test_agent.py`,
   `tests/contract/test_agent_tools.py` y `scripts/verify_demo.py`.
2. **Hito B (Fases 3–4):** el mismo escenario vive en PostgreSQL, puede
   inyectarse y se visualiza/consulta con referencias verificables.
3. **Hito C (Fases 5–6):** patrones nuevos y controles negativos pasan por la
   suite E2E; el agente se evalúa con métricas y un conjunto retenido.
4. **Hito D (Fase 7):** la demo es operable, observable y recuperable.

## Secuencia de trabajo del responsable del agente

1. Liderar Fase 1 y los componentes de Fase 2: protocolo, herramientas,
   fallback, pasos, evidencia y evaluación de hallazgos.
2. Acordar con datos/plataforma las interfaces de Fase 3 antes de depender de
   PostgreSQL; usar repositorios por protocolo para conservar pruebas locales.
3. Colaborar en Fase 4 para que Q&A, timeline y grafo consuman los IDs que
   produce el investigador, no representaciones paralelas.
4. En Fase 5, definir con detección los answer keys y usar sólo esa evidencia
   validada para los ejemplos de entrenamiento.
5. Ser responsable de las métricas y la promoción de versiones de agente en
   Fase 6; plataforma opera presupuesto, telemetría y failover de Fase 7.

## Definición final de listo

El agente de consultoría estará listo para demo cuando un juez pueda introducir
un escenario no mostrado, el sistema detecte y priorice un lead, el agente
trace fondos con herramientas válidas, exponga la cadena de evidencia,
distinga entre acusación sustentada e insuficiente, calcule el monto desde
transacciones raíz y responda preguntas citando los IDs recuperables del caso.
