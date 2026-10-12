// TestFw102CLib.cpp : Defines the entry point for the console application.
//

#include "stdafx.h"
#include <string.h>
#include <memory>
#include<Windows.h>

typedef int (*Fw102C_GetPorts)(char *serialNo);
typedef int (*Fw102C_Open)(char* serialNo, int nBaud, int timeout);
typedef int (*Fw102C_Close)(int hdl);
typedef int (*Fw102C_GetPosition)(int hdl,int& pos);
typedef int (*Fw102C_GetTriggerMode)(int hdl,int& triggermode);
typedef int (*Fw102C_GetPcount)(int hdl,int& poscount);
typedef int (*Fw102C_SetPosition)(int hdl,int pos);
typedef int (*Fw102C_SetTriggerMode)(int hdl,int mode);
Fw102C_GetPorts GetPorts; 
Fw102C_Open Open;
Fw102C_Close Close;
Fw102C_GetPosition GetPosition;
Fw102C_GetTriggerMode GetTrigMode;
Fw102C_GetPcount GetPositionCount;
Fw102C_SetPosition SetPosition;
Fw102C_SetTriggerMode SetTriggerMode;

HINSTANCE hdll;
int pcount;

void GetPos(int hdl)
{
	int value = -1;
	int	ret = GetPosition(hdl,value);
	if(ret == 0)
	{
		printf("current position:%d.\n",value);
	}
}

void SetPos(int hdl,int pos)
{
	if(pos <= 0 || pos > pcount)
	{
		printf("position is invalid,current position count is %d\n",pcount);
		return;
	}
	int ret = SetPosition(hdl,pos);
	if(ret == 0)
	{
		printf("set position success\n");
	}
	else
	{
		printf("set position failed\n");
	}
}


void GetTriggerMode(int hdl)
{
	int value = -1;
	int	ret = GetTrigMode(hdl,value);
	if(ret == 0)
	{
		printf("current trigger mode:%d.\n",value);
	}
}

void SetTriMode(int hdl,int mode)
{
	int ret = SetTriggerMode(hdl,mode);
	if(ret == 0)
	{
		printf("set trigger mode success\n");
	}
	else
	{
		printf("set trigger mode failed\n");
	}
}

int Init()
{	
	hdll = LoadLibrary(TEXT("FilterWheel102_win32.dll"));
	if(hdll== NULL)
	{
		printf_s("Load FilterWheel102_win32.dll,please check\n");	
		return -1;
	}
	GetPorts = (Fw102C_GetPorts)GetProcAddress(hdll, "GetPorts");
	Open = (Fw102C_Open)GetProcAddress(hdll, "Open");
	Close = (Fw102C_Close)GetProcAddress(hdll, "Close");
	GetPosition = (Fw102C_GetPosition)GetProcAddress(hdll, "GetPosition");
	GetTrigMode = (Fw102C_GetTriggerMode)GetProcAddress(hdll, "GetTriggerMode");
	GetPositionCount = (Fw102C_GetPcount)GetProcAddress(hdll, "GetPositionCount");
	SetPosition = (Fw102C_SetPosition)GetProcAddress(hdll, "SetPosition");
	SetTriggerMode = (Fw102C_SetTriggerMode)GetProcAddress(hdll, "SetTriggerMode");

	if(GetPorts == NULL || Open == NULL || Close == NULL ||GetPosition == NULL || GetTrigMode == NULL||SetPosition== NULL||SetTriggerMode == NULL)
	{
		printf_s("Load FilterWheel102_win32.dll,please check\n");	
		return -1;
	}
	return 0;
}


int _tmain(int argc, _TCHAR* argv[])
{
	if(Init() < 0)
	{
		return 0;
	}
	char sn[256];
	memset(sn,0,sizeof(sn));
	GetPorts(sn);
	sscanf_s(sn,"%[^,]", sn, 256);
	printf("com port : %s.\n",sn);
	int hdl=Open(sn,115200,10);
    GetPositionCount(hdl,pcount);
	int ret = -1;
	int value = -1;

	if(hdl < 0 )
	{ 
		printf("com port fails, please check the driver installed correctly\n");
	}
	else
	{
		char b='e';
		char str[256];
		memset(str,0,sizeof(str));
		printf("0: get position	1: set position	2: get trigger mode	3: set trigger mode (press 'x' to quit)\n");
		while(b != 'x')
		{
			if(b != '\n')
			{
				printf("please select to continue:\n");	
			}
			b = getchar();
			switch (b)
			{
			case '0':
				GetPos(hdl);
				break;
			case '1':
				printf("input position:\n");	
				scanf("%s",str);
				value = atoi(str);
				SetPos(hdl,value);
				break;
			case '2':
				GetTriggerMode(hdl);
				break;
			case '3':
				printf("input trigger mode(0 or 1):\n");	
				scanf("%s",str);
				int size;
				size = strlen(str);
				if(size == 1 && (str[0] == '0' || str[0] == '1'))
				{				
					value = atoi(str);
					SetTriMode(hdl,value);
				}
				else
				{
					printf("invalid input,please input again\n");	
				}
				break;
			default:
				break;
			}
			ret = -1;
			value = -1;
			memset(str,0,sizeof(str));
		}
		Close(hdl);
		return 0;
	}
}
