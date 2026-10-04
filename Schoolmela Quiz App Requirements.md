# **Requirements Document for Schoolmela Quiz Web Application**

## **1\. Introduction**

This document outlines the requirements for a web application designed for rural school children aged 12-15 to take timed quizzes and generate scores. The application supports two user roles: Students and Admins, providing functionalities for quiz participation, management, and reporting. The system is intended to be user-friendly, accessible, and suitable for low-resource environments.

## **2\. Scope**

The application will:

* Allow students to register, log in, take timed quizzes, and view scores.  
* Enable admins to manage users, create quizzes, assign quizzes, and review results.  
* Be available as a web-based platform and an Android mobile application, optimized for simplicity and accessibility on basic devices with limited internet connectivity.  
* Ensure data security for user credentials and quiz results.
* Support teacher-hosted live quiz rooms with WebSocket question delivery and student answers.

## **2.1 Technology Stack & Architecture**

* **Backend**: Python, FastAPI, SQLAlchemy, Alembic, managed with uv.
* **Web Frontend**: React.  
* **Mobile Frontend**: Flutter  
* **Architecture**: Cloud Native architecture, designed for containerized deployment across any cloud provider.  
* **Local Environment**: Full support for local development and execution using Docker / Docker Compose.

## **3\. User Roles**

### **3.1 Student**

* **Description**: Rural school children aged 12-15 who participate in quizzes.  
* **Key Functionalities**:  
  * Register and log in/out.  
  * View and take assigned quizzes.  
  * View quiz scores.

### **3.2 Admin**

* **Description**: Teachers or school staff managing the quiz system.  
* **Key Functionalities**:  
  * View registered users.  
  * Create and manage multiple-choice questions and quizzes.  
  * Assign quizzes to students.  
  * View submitted quizzes and scores.

## **4\. Functional Requirements**

### **4.1 Student Features**

#### **4.1.1 User Registration**

* Students can sign up by providing mandatory and optional information:  
  * Student name (mandatory).  
  * Mobile number (mandatory).  
  * PIN (mandatory, 4-6 digits).  
  * Email address (optional).  
  * School name (optional).  
* System validates input and confirms successful registration.  
* PINs are stored securely (hashed).

#### **4.1.2 User Login/Logout**

* Students log in using a simplified authentication method with their mobile number and PIN.  
* System authenticates credentials and redirects to the student dashboard.  
* Invalid credentials display an error message.  
* Logout option terminates the session.

#### **4.1.3 View Assigned Quizzes**

* Dashboard displays a list of assigned quizzes with:  
  * Quiz title.  
  * Number of questions.  
  * Total time limit (if applicable).  
* Students can select a quiz to start.

#### **4.1.4 Take Quiz**

* Each quiz consists of multiple-choice questions (4 options, one correct answer).  
* Each question has an individual time limit (e.g., 30-60 seconds, configurable by admin).  
* Timer is displayed for each question.  
* Students select an answer and submit before the time limit.  
* Only correct answers submitted within the time limit are scored.  
* Once submitted, students cannot revisit the question.  
* Quiz ends when all questions are answered or the total quiz time (if set) expires.

#### **4.1.5 View Score**

* After quiz completion, students see:  
  * Total score (e.g., 8/10 correct answers).  
  * Percentage score.  
  * Correct/incorrect answers for each question (optional, admin-configurable).  
* Scores are saved and accessible in the student’s dashboard history.

### **4.2 Admin Features**

#### **4.2.1 View Registered Users**

* Admin dashboard displays a list of registered students with:  
  * Student name and mobile number.  
  * Registration date.  
  * Option to deactivate accounts (if needed).

#### **4.2.2 Create Multiple-Choice Questions**

* Admins can create questions with:  
  * Question text (up to 500 characters).  
  * Four answer options (one correct, marked by admin).  
  * Time limit per question (e.g., 30-120 seconds).  
* Questions are saved in a question bank for reuse.  
* Admins can edit or delete existing questions.

#### **4.2.3 Create Quizzes**

* Admins can create quizzes by:  
  * Selecting questions from the question bank.  
  * Setting a quiz title.  
  * Optionally setting a total quiz time limit.  
* Quizzes are saved and can be edited or deleted.

#### **4.2.4 Assign Quizzes**

* Admins can assign quizzes to:  
  * Individual students.  
  * Groups of students (e.g., all registered users).  
* System notifies students of new assignments (e.g., via dashboard update).

#### **4.2.5 View Submitted Quizzes**

* Admins can view:  
  * List of submitted quizzes by student and quiz title.  
  * Individual student scores (e.g., 8/10, 80%).  
  * Detailed results (correct/incorrect answers per question, time taken per question).  
* Option to export results as a CSV file (e.g., student name, mobile number, quiz title, score).

### **4.3 General Features**

#### **4.3.1 User Interface**

* Simple, intuitive design optimized for low-literacy users.  
* Large buttons, clear fonts, and minimal text.  
* Responsive web design for desktop/mobile browsers and a native Android mobile application interface.

#### **4.3.2 Accessibility**

* Support for basic devices (e.g., low-end smartphones, tablets).  
* Minimal data usage for low-bandwidth environments.  
* Offline mode for quiz-taking (if feasible, with sync when online).

#### **4.3.3 Security**

* Secure user authentication (hashed PINs, session management).  
* Role-based access control (students cannot access admin features).  
* Protection against common web vulnerabilities (e.g., XSS, SQL injection).

## **5\. Non-Functional Requirements**

### **5.1 Performance**

* Page load time \< 3 seconds on 3G connections.  
* Support up to 100 concurrent users (e.g., a small rural school).

### **5.2 Scalability**

* System can handle up to 1,000 registered students and 100 quizzes.  
* Database optimized for quick retrieval of quiz and score data.

### **5.3 Reliability**

* 99% uptime for the web application.  
* Data backup every 24 hours.

### **5.4 Usability**

* Onboarding tutorial or tooltips for first-time users.  
* Error messages in simple language (e.g., “Wrong PIN, try again”).

### **5.5 Compatibility**

* Compatible with modern web browsers (e.g., Chrome, Firefox, Safari) and supports Android devices via the native mobile app.  
* Minimum requirements: 1GB RAM, 3G internet.

### **5.6 Deployment & Infrastructure**

* Cloud Native containerized deployment suitable for any cloud hosting provider.  
* Seamless local environment setups via Docker and Docker Compose for developer workflows and testing.

## **6\. Constraints**

* No support for non-Latin languages initially (English only).  
* No integration with external systems (e.g., school management software).  
* Limited to multiple-choice questions (no open-ended or other formats).

## **7\. Assumptions**

* Students have access to basic internet-enabled devices (e.g., shared school tablets).  
* Admins are trained to use the system.  
* Internet connectivity is intermittent but available at least once daily for syncing.

## **8\. Future Enhancements**

* Support for additional question types (e.g., true/false, fill-in-the-blank).  
* Multilingual interface for regional languages.  
* Gamification features (e.g., badges, leaderboards).  
* Analytics dashboard for admins to track student progress over time.

## **9\. Deliverables**

* Web application with student and admin interfaces.  
* User documentation (simple guides for students and admins).  
* Admin training materials (if required).  
* Source code and deployment instructions.

## **10\. Acceptance Criteria**

* All functional requirements are implemented and tested.  
* System passes usability testing with at least 10 students and 2 admins.  
* No critical bugs (e.g., data loss, security breaches).  
* Application performs reliably on low-end devices in a simulated rural environment.

