# A helper that cannot open its log must terminate the MPI job, not wait in MPI_Finalize
# while the leader waits for Ready. Keep a successful control run to catch launcher failures.
file(MAKE_DIRECTORY "${TEST_DIR}" "${TEST_DIR}/blocked.log.rank1")
file(WRITE "${TEST_DIR}/a.mtx" "%%MatrixMarket matrix coordinate real symmetric\n100 100 100\n")
foreach(i RANGE 1 100)
  file(APPEND "${TEST_DIR}/a.mtx" "${i} ${i} ${i}\n")
endforeach()
foreach(case control blocked)
  execute_process(
    COMMAND "${MPIEXEC}" "${MPI_NUMPROC_FLAG}" 3 ${MPI_FLAGS} "${HSOLVE_MPI}"
      --A "${TEST_DIR}/a.mtx" --sigma 40.5 --k 4 --helper-counts on --threads 1 --quiet
      --log "${TEST_DIR}/${case}.log" --out "${TEST_DIR}/${case}"
    RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error TIMEOUT 20)
  if(case STREQUAL "control")
    if(NOT "${result}" STREQUAL "0")
      message(FATAL_ERROR "MPI control failed (${result}): ${output}\n${error}")
    endif()
  elseif(NOT "${result}" STREQUAL "2" OR NOT error MATCHES "cannot open log file")
    message(FATAL_ERROR "helper failure must exit 2 without hanging (${result}): ${output}\n${error}")
  endif()
endforeach()
