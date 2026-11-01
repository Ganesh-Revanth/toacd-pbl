#include <iostream>
#include <string>
#include <vector>
#include <numeric>
#include <algorithm>
#include <iomanip>
#include <map>

struct CourseGrade {
    std::string courseCode;
    int creditHours;
    double numericScore;

    CourseGrade(std::string code, int credits, double score)
        : courseCode(std::move(code)), creditHours(credits), numericScore(score) {}

    double getGradePoints() const {
        if (numericScore >= 90.0) return 4.0;
        if (numericScore >= 80.0) return 3.0;
        if (numericScore >= 70.0) return 2.0;
        if (numericScore >= 60.0) return 1.0;
        return 0.0;
    }
};

enum class AcademicStanding { SUMMA_CUM_LAUDE, DEANS_LIST, GOOD_STANDING, PROBATION };

class StudentTranscript {
private:
    std::string studentId;
    std::string studentName;
    std::string major;
    std::vector<CourseGrade> courses;

public:
    StudentTranscript(std::string id, std::string name, std::string maj = "Computer Science")
        : studentId(std::move(id)), studentName(std::move(name)), major(std::move(maj)) {}

    void addCourse(const CourseGrade& cg) { courses.push_back(cg); }

    int getTotalCredits() const {
        int total = 0;
        for (const auto& c : courses) total += c.creditHours;
        return total;
    }

    double calculateGPA() const {
        double totalPoints = 0.0;
        int totalCredits = 0;
        for (const auto& c : courses) {
            totalPoints += c.getGradePoints() * c.creditHours;
            totalCredits += c.creditHours;
        }
        return (totalCredits > 0) ? (totalPoints / totalCredits) : 0.0;
    }

    AcademicStanding getStanding() const {
        double gpa = calculateGPA();
        if (gpa >= 3.9 && getTotalCredits() >= 10) return AcademicStanding::SUMMA_CUM_LAUDE;
        if (gpa >= 3.5 && getTotalCredits() >= 10) return AcademicStanding::DEANS_LIST;
        if (gpa >= 2.0) return AcademicStanding::GOOD_STANDING;
        return AcademicStanding::PROBATION;
    }

    const std::string& getName() const { return studentName; }
    const std::string& getId() const { return studentId; }
    const std::string& getMajor() const { return major; }
    const std::vector<CourseGrade>& getCourses() const { return courses; }

    void printTranscriptReport() const {
        std::cout << "\n---------------- STUDENT TRANSCRIPT ----------------\n";
        std::cout << "Student: " << studentName << " (ID: " << studentId << ")\n";
        std::cout << "Major  : " << major << "\n";
        std::cout << "Courses Completed:\n";
        for (const auto& c : courses) {
            std::cout << "  * [" << std::setw(8) << std::left << c.courseCode << "] "
                      << c.creditHours << " credits | Score: " << c.numericScore
                      << " | Points: " << c.getGradePoints() << "\n";
        }
        std::cout << "Total Credits Earned: " << getTotalCredits() << "\n";
        std::cout << "Cumulative GPA      : " << std::fixed << std::setprecision(2) << calculateGPA() << "\n";
        std::cout << "Honor Standing      : " << standingToString(getStanding()) << "\n";
        std::cout << "----------------------------------------------------\n";
    }

private:
    static const char* standingToString(AcademicStanding s) {
        switch (s) {
            case AcademicStanding::SUMMA_CUM_LAUDE: return "Summa Cum Laude";
            case AcademicStanding::DEANS_LIST:     return "Dean's Honor Roll";
            case AcademicStanding::GOOD_STANDING:  return "Good Academic Standing";
            case AcademicStanding::PROBATION:      return "Academic Probation";
            default: return "Unknown";
        }
    }
};

class DepartmentAnalyticsRegistry {
private:
    std::vector<StudentTranscript> studentRoster;

public:
    void enrollStudent(const StudentTranscript& s) {
        studentRoster.push_back(s);
    }

    double computeDepartmentAverageGPA() const {
        if (studentRoster.empty()) return 0.0;
        double sum = 0.0;
        for (const auto& s : studentRoster) sum += s.calculateGPA();
        return sum / studentRoster.size();
    }

    void printHonorRoll() const {
        std::cout << "\n================ DEAN'S HONOR ROLL ================\n";
        for (const auto& s : studentRoster) {
            if (s.calculateGPA() >= 3.5) {
                std::cout << "  Honoree: " << std::setw(20) << std::left << s.getName()
                          << " | Major: " << std::setw(18) << s.getMajor()
                          << " | GPA: " << s.calculateGPA() << "\n";
            }
        }
        std::cout << "===================================================\n";
    }
};

int main() {
    DepartmentAnalyticsRegistry dept;

    StudentTranscript s1("STU-01", "Grace Hopper", "Computer Science");
    s1.addCourse(CourseGrade("CS101", 4, 95.0));
    s1.addCourse(CourseGrade("CS201", 4, 92.0));
    s1.addCourse(CourseGrade("MATH301", 3, 88.0));
    s1.printTranscriptReport();
    dept.enrollStudent(s1);

    StudentTranscript s2("STU-02", "Donald Knuth", "Mathematics");
    s2.addCourse(CourseGrade("CS101", 4, 98.0));
    s2.addCourse(CourseGrade("CS201", 4, 99.0));
    s2.addCourse(CourseGrade("MATH301", 3, 100.0));
    s2.printTranscriptReport();
    dept.enrollStudent(s2);

    StudentTranscript s3("STU-03", "Claude Shannon", "Information Theory");
    s3.addCourse(CourseGrade("CS101", 4, 94.0));
    s3.addCourse(CourseGrade("EE201", 4, 96.0));
    s3.addCourse(CourseGrade("MATH301", 3, 91.0));
    s3.printTranscriptReport();
    dept.enrollStudent(s3);

    dept.printHonorRoll();
    std::cout << "Overall Department Average GPA: " << dept.computeDepartmentAverageGPA() << "\n";
    return 0;
}
