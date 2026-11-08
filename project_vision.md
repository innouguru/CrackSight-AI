**Project vision**

Develop an AI-powered building inspection system that detects visible cracks on painted and unpainted walls, analyzes their characteristics, estimates their dimensions when sufficient calibration is available, and assesses whether they warrant further attention.

**Initial target environment**

- Painted interior and exterior building walls.
- Unpainted plaster, concrete, and masonry walls.
- Residential and other buildings, with broader coverage introduced as the dataset grows.

**Core capabilities**

1. Detect visible cracks in photographs.
2. Locate and outline detected cracks.
3. Analyze crack shape, orientation, branching, and apparent dimensions.
4. Estimate physical crack dimensions when appropriate image calibration is available.
5. Assess the apparent level of concern using visual evidence, measurements, and contextual information.
6. Explain the assessment and recommend appropriate next steps.
7. Identify unsuitable images and cases requiring professional assessment.

**Development strategy**

Begin with a software prototype using public datasets and an ordinary computer or smartphone. Validate the model on real building-wall images before developing a dedicated inspection device.

**Budget constraint**

Prioritize free datasets, open-source machine learning tools, existing computing resources, and carefully controlled data collection.

**Safety boundary**

The system is an inspection aid. Its image-based assessment must not be represented as proof that a building is structurally safe or unsafe.

**Initial technical objective**

Establish a reliable crack-detection baseline and determine whether the available data supports the intended measurement and severity-assessment tasks.