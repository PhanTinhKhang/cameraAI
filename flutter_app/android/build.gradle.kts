allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    afterEvaluate {
        val androidExt = extensions.findByName("android")
        if (androidExt != null) {
            try {
                // Using reflection to avoid importing Android Gradle Plugin classes directly
                val setCompileSdkMethod = androidExt.javaClass.getMethod("setCompileSdkVersion", Int::class.java)
                setCompileSdkMethod.invoke(androidExt, 36)
            } catch (e: Exception) {
                // Ignore if method not found
                try {
                    val setCompileSdkMethod = androidExt.javaClass.getMethod("setCompileSdk", Int::class.java)
                    setCompileSdkMethod.invoke(androidExt, 36)
                } catch (e: Exception) {}
            }
        }
    }
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
