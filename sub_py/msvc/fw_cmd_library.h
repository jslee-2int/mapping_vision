#pragma once
#include <memory>
#include "stdafx.h"
using namespace std;

/// <summary>
/// list all the possible port on this computer.
/// </summary>
/// <param name="serialNo">port list returned string include serial number and device descriptor, seperated by comma</param>
/// <returns>non-negtive number: number of device in the list; negtive number : failed.</returns>
DllExport int GetPorts(char *serialNo);

/// <summary>
///  open port function.
/// </summary>
/// <param name="serialNo">serial number of the device to be opened, use GetPorts function to get exist list first.</param>
/// <param name="nBaud">bit per second of port</param>
/// <param name="timeout">set timeout value in (s)</param>
/// <returns> non-negtive number: hdl number returned successfully; negtive number : failed.</returns>
DllExport int Open(char* serialNo, int nBaud, int timeout);

/// <summary>
/// check opened status of port
/// </summary>
/// <param name="serialNo">serial number of the device to be checked.</param>
/// <returns> 0: port is not opened; 1 : port is opened.</returns>
DllExport int IsOpen(char *serialNo);

/// <summary>
/// close current opend port
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <returns> 0: success; negtive number : failed.</returns>
DllExport int Close(int hdl);

/// <summary>
/// <p>set fiterwheel's timeout</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="timeout">timeout</param>
/// <returns>
/// <p>0: success;</p>
/// </returns>
DllExport int SetTimeout(int hdl,int timeout);

/// <summary>
/// <p>set fiterwheel's position to pos</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="pos">fiterwheel position</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetPosition(int hdl,int pos);

/// <summary>
/// <p>set fiterwheel's position count to count</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="count">fiterwheel PositionCount</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetPositionCount(int hdl,int count);

/// <summary>
/// <p>set fiterwheel's speed to speed</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="speed">fiterwheel speed</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetSpeed(int hdl,int speed);

/// <summary>
/// <p>set fiterwheel's trigger mode to mode</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="mode">fiterwheel trigger mode</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetTriggerMode(int hdl,int mode);

/// <summary>
/// <p>set fiterwheel's min velocity to min</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="min">fiterwheel min velocity</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetMinVelocity(int hdl,int min);

/// <summary>
/// <p>set fiterwheel's max velocity to max</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="max">fiterwheel max velocity</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetMaxVelocity(int hdl,int max);

/// <summary>
/// <p>set fiterwheel's acceleration to acceleration</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="acceleration">fiterwheel acceleration</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetAcceleration(int hdl,int acceleration);

/// <summary>
/// <p>set fiterwheel's sensor mode to mode</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="mode">fiterwheel sensor mode</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int SetSensorMode (int hdl,int mode);

/// <summary>
/// <p>save all the settings as default on power up </p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int Save(int hdl);

/// <summary>
/// <p>get the fiterwheel current position</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="pos">fiterwheel actual position</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetPosition(int hdl,int& pos);

/// <summary>
/// <p>get the fiterwheel current position count</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="poscount">fiterwheel actual position count</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetPositionCount(int hdl,int& poscount);

/// <summary>
/// <p>get the fiterwheel current speed</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="speed">fiterwheel actual speed</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetSpeed(int hdl,int& speed);

/// <summary>
/// <p>get the fiterwheel current trigger mode</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="triggermode">fiterwheel actual trigger mode</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetTriggerMode(int hdl,int& triggermode);

/// <summary>
/// <p>get the fiterwheel current min velocity</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="minvelocity">fiterwheel actual min velocity</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetMinVelocity(int hdl,int& minvelocity);

/// <summary>
/// <p>get the fiterwheel current max velocity</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="maxvelocity">fiterwheel actual max velocity</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetMaxVelocity(int hdl,int& maxvelocity);

/// <summary>
/// <p>get the fiterwheel current acceleration</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="acceleration">fiterwheel actual acceleration</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetAcceleration(int hdl,int& acceleration);

/// <summary>
/// <p>get the fiterwheel current sensor mode</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="sensormode">fiterwheel actual sensor mode</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetSensorMode (int hdl,int& sensormode);

/// <summary>
/// <p>get the fiterwheel current sensor mode</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="time">the time from last position to current position</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetTimeToCurrentPos (int hdl,int& time);

/// <summary>
/// <p>get the fiterwheel id</p>
/// <p>make sure the port was opened successful before call this function.</p>
/// <p>make sure this is the correct device by checking the ID string before call this function.</p>
/// </summary>
/// <param name="hdl">handle of port.</param>
/// <param name="d">output string (<255)</param>
/// <returns>
/// <p>0: success;</p>
/// <p>0xEA: CMD_NOT_DEFINED;</p>
/// <p>0xEB: time out;</p>
/// <p>0xED: invalid string buffer;</p>
/// </returns>
DllExport int GetId(int hdl,char* d);
