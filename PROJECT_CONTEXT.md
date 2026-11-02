# PROJECT CONTEXT

## Project Purpose

Transition from model development to a practical, public-facing AI-assisted building inspection web application that enables non-structural-engineers to detect visible cracks in building photographs and obtain AI-assisted crack segmentation results for inspection purposes.

## Current Product Direction

Building a responsive, public web application for building inspection that supports:

- **Guest users**: Try the application without registration (3 analyses per session, 24-hour expiration)
- **Registered users**: Create and save inspections, generate PDF reports (generous monthly allowance)
- **Initial structural components**: Walls, beams, columns
- **Inspection workflow**: Create new or add to existing inspections, save results, manually mark as Completed
- **Output format**: Original image, predicted crack mask, overlay, pixel measurements, model version, AI vs observation distinction

## Technology Stack

**Frontend**:
- React with TypeScript
- Responsive web interface (desktop, tablet, mobile)

**Backend**:
- Python FastAPI
- Neon PostgreSQL (database)
- Cloudflare R2 (object storage)
- Clerk (authentication - email/password + Google)

**Inference Service**:
- Separate private inference API
- U-Net ResNet-34 encoder model (baseline B1)
- CPU inference with configurable timeouts and error handling

## Existing Model and Completed Milestones

### Completed Work

**M1 - Dataset Ingestion Pipeline**:
- Professional dataset loader with binary mask conversion
- Manifest-based data contract validation
- Three datasets: façade-crack-dataset, crack-seg, concrete400
- Deduplication and validation mechanisms
- Audit trail and evidence preservation

**M3 - Baseline Model Development**:
- UNetResNet34 architecture (ResNet-34 encoder + decoder)
- Baseline B1 training on crack-seg and concrete400 datasets
- Input size: 256×256 RGB, preprocessing: RGB→bilinear resize→/255→CHW
- Output activation: sigmoid, threshold: 0.5
- Checkpoint: `model_artifacts/m3_crack_seg_baseline_b1_20261026_201725/best_model.pth`

**M2 - Inference Pipeline**:
- Reusable `CrackSegmentationPipeline` with `InferenceConfig`
- Returns `original_image`, `probability_map`, `binary_mask`, `overlay`
- Error handling for missing/corrupted files
- Unit tests covering architecture compatibility, preprocessing, output dimensions

### Current Evaluation Results

- Mean Dice: 0.7242
- Mean IoU: 0.5884
- Precision: 0.7379
- Recall: 0.7758
- Test set: 111 scored records (after duplicate exclusion)

## Important Decisions

### Architecture Decisions
1. **Two-tier API**: Public FastAPI backend + private inference service for isolation and scalability
2. **CPU-first**: Inference service runs on CPU, no GPU dependency
3. **No ORM**: Straightforward database access for maintainability
4. **Guest session isolation**: Cloudflare R2 storage with automatic 24-hour expiration
5. **Prediction versioning**: Preserve previous predictions for reanalysis rather than overwriting

### Product Scope Decisions
1. **Inspection-focused**: Not a model evaluation platform
2. **Pixel measurements only**: No physical calibration initially
3. **Simple workflow**: Two statuses (Draft, Completed) for simplicity
4. **No editing**: No manual segmentation-mask correction
5. **Safe disclaimers**: Clear distinction between AI predictions and professional engineering

## Constraints and Exclusions

### Technical Constraints
- Limited budget (prefer free-tier services where possible)
- No GPU assumption (CPU inference initially)
- Model checkpoint must not be committed (existing .gitignore)
- Inference service hosting remains unresolved (requires research)
- Large image resizing for inference, but preserve original
- Configurable file-size and dimension limits

### Product Exclusions (Initial Version)
- Model evaluation workspace
- Reference-mask uploads
- CSV research exports
- Manual segmentation-mask correction
- Physical crack measurement or calibration
- Structural safety certification
- Engineering recommendations
- Organization-level multi-user collaboration
- Publicly shareable report links
- Complex inspection workflow states
- Visual prominence classification
- Physical dimension measurements (millimetres, centimetres)

## Current Project Status

**Phase 1 Complete**: Comprehensive inspection of existing project architecture and code
- All existing codebases reviewed and functional
- Inference pipeline verified with unit tests
- Model checkpoint and evaluation report preserved
- Dataset ingestion pipeline functional

**Phase 2**: Documentation only milestone (this phase)
- Creating comprehensive documentation for application development
- Preserving existing implementation
- No code changes or new implementations

## Open Decisions

1. **Inference Service Hosting**: Research and select CPU inference provider (unresolved - requires benchmarking)
2. **File Size Limits**: Configure maximum file sizes and dimensions for uploads
3. **PDF Report Branding**: Specify application branding elements for reports
4. **Measurement Precision**: Determine acceptable precision for pixel measurements
5. **Batch Processing**: Configure batch processing limits and retry logic
6. **Cleanup Strategy**: Specify partial failure handling for inspection deletion
7. **Guest Session Management**: Implement automatic cleanup of abandoned uploads
8. **Storage Access Patterns**: Document secure object storage access and ownership

## Documentation Links

- [APP_SPECIFICATION.md](./APP_SPECIFICATION.md) - Defines application requirements and user workflows
- [TECHNICAL_DESIGN.md](./TECHNICAL_DESIGN.md) - Explains implementation approach and architecture
- [ROADMAP.md](./ROADMAP.md) - Provides development roadmap from existing project state

## Verification Summary

- ✅ Existing model work preserved (no modifications)
- ✅ No application implementation changes
- ✅ All existing files maintained
- ✅ Documentation focuses on new product development
- ✅ Product direction clearly specified (inspection aid, not engineering tool)
