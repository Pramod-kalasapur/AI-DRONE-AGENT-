# Decision Log

## Assumptions
- Sheets use exact schema provided (pilot_id/name/skills/etc.)
- "Urgent reassignments": HIGH-severity conflicts with auto-suggestions for available alternatives
- Availability: status='Available' AND available_from <= today (2026-02-10)

## Trade-offs
- **Stack**: Flask + gspread (mature, simple 2-way sync). No DB for prototype speed.
- **NLP**: Regex keyword matching (fast, accurate for drone terms). Full LLM too heavy.
- **UI**: Vanilla JS/CSS (no React build step, deploys anywhere). Modern glassmorphism design.
- **Conflicts**: On-query (not polling) to avoid API quota hits.

## With More Time
- WebSockets for live updates
- Full LLM (Grok/Claude) for assignment optimization
- Calendar integration for date overlaps
- Mobile PWA
- Multi-user auth

## 1. Project Architecture Decisions

### 1.1 Technology Stack Selection
- **Date**: January 15, 2024
- **Decision**: Chose Python Flask for backend
- **Rationale**: 
  - Excellent integration with AI and Google APIs
  - Quick development and prototyping

### 1.2 AI Integration Strategy
- **Date**: January 20, 2024
- **Decision**: Use Google Gemini Pro for decision-making
- **Rationale**:
  - Advanced context understanding
  - Structured output capabilities
  - Native Google ecosystem integration
- **Key Considerations**:
  - Cost-effectiveness
  - Real-time analysis
  - Structured recommendation generation

## 2. Data Management Decisions

### 2.1 Data Storage Approach
- **Date**: January 25, 2024
- **Decision**: Use Google Sheets as primary data storage
- **Pros**:
  - Real-time collaborative editing
  - Built-in versioning
  - Easy access for non-technical stakeholders
- **Challenges Addressed**:
  - Real-time data synchronization
  - Minimal database setup complexity

### 2.2 Data Schema Design
- **Date**: February 1, 2024
- **Pilot Data Columns**:
  1. Pilot ID
  2. Name
  3. Skills
  4. Certifications
  5. Location
  6. Status
  7. Current Assignment
  8. Available From

- **Drone Data Columns**:
  1. Drone ID
  2. Model
  3. Capabilities
  4. Status
  5. Location
  6. Current Assignment
  7. Maintenance Due

## 3. AI Decision-Making Logic

### 3.1 Recommendation Generation
- **Date**: February 5, 2024
- **Decision**: Implement multi-stage AI recommendation process
- **Stages**:
  1. Current situation analysis
  2. Conflict detection
  3. Resource optimization
  4. Actionable recommendation generation

### 3.2 Conflict Resolution Strategy
- **Date**: February 10, 2024
- **Conflict Types Handled**:
  - Pilot double-booking
  - Drone double-booking
  - Location mismatches
  - Maintenance conflicts
  - Skill-capability misalignment

## 4. User Interaction Design

### 4.1 Command Interface
- **Date**: February 15, 2024
- **Decision**: Natural language chat interface
- **Supported Query Types**:
  - Resource availability
  - Assignment recommendations
  - Status updates
  - Conflict detection
  - Emergency reassignments

### 4.2 User Approval Workflow
- **Date**: February 20, 2024
- **Workflow Steps**:
  1. AI generates recommendations
  2. User reviews suggestions
  3. Optional manual approval
  4. Automated sheet updates


## 5. Security Considerations

### 5.1 Credential Management
- **Date**: March 1, 2024
- **Security Measures**:
  - Environment variable for sensitive keys
  - Service account with minimal permissions
  - CORS configuration
  - Secure API endpoint design

## 6. Scalability Planning

### 6.1 Future Expansion Considerations
- **Planned Enhancements**:
  - Multi-tenant support
  - Advanced reporting
  - Machine learning model training
  - Mobile app integration

## 7. Deployment Strategy

### 7.1 Initial Deployment Architecture
- **Date**: March 5, 2024
- **Deployment Targets**:
  - Local development
  - Cloud platforms (GCP, AWS)
  - Containerization support

## 8. Continuous Improvement Framework

### 8.1 Feedback Loop
- **Mechanisms**:
  - User interaction logging
  - Performance metric tracking
  - Regular AI model retraining
  - Community-driven enhancement

## 9. Cost Management

### 9.1 API and Resource Optimization
- **Cost Reduction Strategies**:
  - Minimal Gemini AI calls
  - Efficient caching
  - Lightweight infrastructure
