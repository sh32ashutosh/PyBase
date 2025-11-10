#ifndef CLI_H
#define CLI_H

#ifndef CLIEXPORT
#define CLIAPI __declspec(dllexport)
#else 
    #define CLIAPI __dllspec(dllimport)
#endif 

typedef void * CLIHandle;
#ifdef __cplusplus
extern "C"{
#endif
    CLIAPI CLIHandle create();
    CLIAPI void destroy(CLIHandle handle);
    CLIAPI int displayMsg(char * msg);
    CLIAPI char * getquery();
#ifdef __cplusplus
}
#endif
#endif
